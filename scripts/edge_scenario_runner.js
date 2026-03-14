#!/usr/bin/env node
/**
 * Edge CDP Scenario Runner
 * Connects to existing Edge browser via CDP and executes scenario tests
 * 
 * Completion detection uses multiple signals:
 * - Loading indicator disappears
 * - Send button leaves "Working" state  
 * - Assistant message content stabilizes
 * - Expected content appears (download link, count, etc.)
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const CDP_URL = 'http://127.0.0.1:9223';
const SHELL_URL = 'http://localhost:3000';
const SCREENSHOT_DIR = '/var/home/ff/Documents/CDP_Merged/output/scenario_evidence';

// Ensure screenshot directory exists
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function captureEvidence(page, name) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const screenshotPath = path.join(SCREENSHOT_DIR, `${name}_${timestamp}.png`);
  try {
    await page.screenshot({ path: screenshotPath, timeout: 10000 });
    console.log(`[EVIDENCE] Screenshot captured: ${screenshotPath}`);
    return screenshotPath;
  } catch (e) {
    console.log(`[WARN] Screenshot failed: ${e.message}`);
    return null;
  }
}

async function waitForPageLoad(page) {
  console.log('[WAIT] Waiting for page to load...');
  await page.waitForLoadState('domcontentloaded');
  await sleep(3000);
  console.log('[OK] Page loaded');
}

/**
 * Get the last assistant message from the page
 * Based on DOM structure: .flex.justify-start contains assistant messages
 */
async function getLastAssistantMessage(page) {
  return await page.evaluate(() => {
    // Assistant messages are in .flex.justify-start containers
    const assistantContainers = document.querySelectorAll('.flex.justify-start');
    if (assistantContainers.length === 0) return null;
    
    const lastContainer = assistantContainers[assistantContainers.length - 1];
    const messageDiv = lastContainer.querySelector('.max-w-\[78ch\'], .rounded-\[24px\], [class*="bg-zinc-950"]');
    return messageDiv ? messageDiv.textContent : lastContainer.textContent;
  });
}

/**
 * Get all messages (user and assistant)
 */
async function getAllMessages(page) {
  return await page.evaluate(() => {
    const messages = [];
    const messageContainer = document.querySelector('.space-y-3');
    if (!messageContainer) return messages;
    
    const rows = messageContainer.querySelectorAll(':scope > div');
    for (const row of rows) {
      const isUser = row.classList.contains('justify-end');
      const isAssistant = row.classList.contains('justify-start');
      const contentDiv = row.querySelector('[class*="rounded-"]');
      const text = contentDiv ? contentDiv.textContent : row.textContent;
      
      if (isUser || isAssistant) {
        messages.push({
          role: isUser ? 'user' : 'assistant',
          text: text?.trim() || ''
        });
      }
    }
    return messages;
  });
}

/**
 * Enhanced completion detection with multiple signals
 */
async function waitForResponse(page, options = {}) {
  const maxWaitMs = options.maxWaitMs || 180000; // 3 minutes max
  const stabilityWindowMs = options.stabilityWindowMs || 3000;
  const checkIntervalMs = 1000;
  const maxAttempts = maxWaitMs / checkIntervalMs;
  
  console.log(`[WAIT] Waiting for AI response (max ${maxWaitMs/1000}s, stability ${stabilityWindowMs}ms)...`);
  
  let attempts = 0;
  let lastMessageContent = '';
  let stabilityStartTime = null;
  let startTime = Date.now();
  
  while (attempts < maxAttempts) {
    const state = await page.evaluate(() => {
      // Check for loading indicators (dots/pulse animations)
      const loadingIndicators = document.querySelectorAll('.animate-pulse, .animate-bounce, [class*="loading"], [class*="typing"]');
      const hasLoading = loadingIndicators.length > 0;
      
      // Check send button state - look for "Working" text
      const buttons = document.querySelectorAll('button');
      let buttonWorking = false;
      for (const btn of buttons) {
        if (btn.textContent.toLowerCase().includes('working')) {
          buttonWorking = true;
          break;
        }
      }
      
      // Get last assistant message
      const assistantContainers = document.querySelectorAll('.flex.justify-start');
      let lastAssistantText = '';
      if (assistantContainers.length > 0) {
        const lastContainer = assistantContainers[assistantContainers.length - 1];
        // Look for the message content div
        const contentDiv = lastContainer.querySelector('div[class*="rounded-"], div[class*="border-"]');
        lastAssistantText = contentDiv ? contentDiv.textContent : lastContainer.textContent;
      }
      
      return {
        hasLoading,
        buttonWorking,
        lastAssistantText: lastAssistantText?.substring(0, 2000) || '',
        assistantCount: assistantContainers.length
      };
    });
    
    const hasAssistantMessage = state.lastAssistantText.length > 10;
    const messageChanged = state.lastAssistantText !== lastMessageContent;
    
    if (messageChanged) {
      // Message is still streaming/changing
      lastMessageContent = state.lastAssistantText;
      stabilityStartTime = null;
      if (attempts % 5 === 0) {
        console.log(`[PROGRESS] Streaming... (${state.lastAssistantText.substring(0, 80)}...)`);
      }
    } else if (hasAssistantMessage && !state.hasLoading && !state.buttonWorking) {
      // Message stable, no loading, button ready
      if (stabilityStartTime === null) {
        stabilityStartTime = Date.now();
        console.log(`[STABLE] Message stabilized, waiting ${stabilityWindowMs}ms to confirm...`);
      } else if (Date.now() - stabilityStartTime >= stabilityWindowMs) {
        const elapsed = Date.now() - startTime;
        console.log(`[OK] Response complete in ${elapsed}ms`);
        return { 
          complete: true, 
          content: state.lastAssistantText,
          elapsedMs: elapsed
        };
      }
    }
    
    // Optional: check for specific content patterns
    if (options.waitForPattern && state.lastAssistantText.match(options.waitForPattern)) {
      const elapsed = Date.now() - startTime;
      console.log(`[OK] Response complete (pattern matched) in ${elapsed}ms`);
      return { 
        complete: true, 
        content: state.lastAssistantText,
        elapsedMs: elapsed
      };
    }
    
    await sleep(checkIntervalMs);
    attempts++;
    
    if (attempts % 10 === 0) {
      const elapsed = Math.round(attempts * checkIntervalMs / 1000);
      console.log(`[WAIT] Still waiting... (${elapsed}s elapsed, loading=${state.hasLoading}, working=${state.buttonWorking})`);
    }
  }
  
  const elapsed = Date.now() - startTime;
  console.log(`[TIMEOUT] Max wait exceeded after ${elapsed}ms`);
  return { 
    complete: false, 
    content: lastMessageContent,
    timeout: true,
    elapsedMs: elapsed
  };
}

async function sendMessage(page, text) {
  console.log(`[ACTION] Sending message: "${text}"`);
  
  // Find textarea
  const textarea = await page.$('textarea');
  if (!textarea) {
    console.error('[ERROR] No textarea found');
    return false;
  }
  
  await textarea.scrollIntoViewIfNeeded();
  await textarea.click();
  await textarea.fill(text);
  await sleep(300);
  
  // Press Enter to send
  await textarea.press('Enter');
  console.log('[OK] Message sent');
  await sleep(500);
  return true;
}

async function runSC14(page) {
  console.log('\n=== SC-14: Export Path Verification ===');
  
  await page.goto(SHELL_URL);
  await waitForPageLoad(page);
  await captureEvidence(page, 'sc14_start');
  
  // Step 1: Find software companies
  await sendMessage(page, 'Find software companies in Antwerp.');
  const searchResult = await waitForResponse(page, { maxWaitMs: 180000 });
  await captureEvidence(page, 'sc14_search_results');
  
  if (!searchResult.complete) {
    console.log('[WARN] Search response may be incomplete or timed out');
  }
  
  console.log(`[INFO] Search response: ${searchResult.content?.substring(0, 150)}...`);
  
  // Step 2: Export to CSV
  await sendMessage(page, 'Export these to CSV.');
  const exportResult = await waitForResponse(page, { 
    maxWaitMs: 180000,
    waitForPattern: /download|csv|file|export/i
  });
  const screenshot = await captureEvidence(page, 'sc14_export_response');
  
  // Get page content to check for download link
  const content = await page.content();
  const pageText = await page.evaluate(() => document.body.innerText);
  
  const hasCorrectPath = content.includes('localhost:3000/downloads/') || 
                         pageText.includes('localhost:3000/downloads/');
  const hasStalePath = content.includes('localhost:8000') || 
                       pageText.includes('localhost:8000');
  
  // Try to find actual download URL
  const downloadMatch = content.match(/localhost:3000\/downloads\/[^"'<>\s]+/) ||
                       pageText.match(/localhost:3000\/downloads\/[^"'<>\s]+/);
  const downloadUrl = downloadMatch ? downloadMatch[0] : null;
  
  console.log(`[VERIFY] Correct path (port 3000): ${hasCorrectPath ? 'YES ✓' : 'NO ✗'}`);
  console.log(`[VERIFY] Stale path (port 8000): ${hasStalePath ? 'FOUND ✗' : 'NONE ✓'}`);
  console.log(`[VERIFY] Download URL found: ${downloadUrl || 'NONE'}`);
  
  return {
    scenario: 'SC-14',
    correctPath: hasCorrectPath,
    noStalePath: !hasStalePath,
    downloadUrl,
    searchResponse: searchResult.content?.substring(0, 300),
    exportResponse: exportResult.content?.substring(0, 300),
    searchTimeMs: searchResult.elapsedMs,
    exportTimeMs: exportResult.elapsedMs,
    screenshot
  };
}

async function runSC17(page) {
  console.log('\n=== SC-17: Context Reuse (Count Follow-up) ===');
  
  await page.goto(SHELL_URL);
  await waitForPageLoad(page);
  await captureEvidence(page, 'sc17_start');
  
  // Step 1: Find restaurant companies
  await sendMessage(page, 'Find restaurant companies in Gent.');
  const searchResult = await waitForResponse(page, { maxWaitMs: 180000 });
  await captureEvidence(page, 'sc17_search_results');
  
  console.log(`[INFO] Search response: ${searchResult.content?.substring(0, 150)}...`);
  
  // Step 2: Count follow-up - this tests context reuse
  await sendMessage(page, 'How many is that exactly?');
  const countResult = await waitForResponse(page, { 
    maxWaitMs: 180000,
    waitForPattern: /\d+/  // Wait for a number
  });
  const screenshot = await captureEvidence(page, 'sc17_count_response');
  
  const responseText = countResult.content || '';
  const numberMatch = responseText.match(/(\d[\d,]*)/);
  const count = numberMatch ? numberMatch[1].replace(/,/g, '') : null;
  
  console.log(`[VERIFY] Count found: ${count !== null ? count : 'NO'}`);
  console.log(`[RESPONSE] ${responseText.substring(0, 200)}...`);
  
  return {
    scenario: 'SC-17',
    contextReused: count !== null,
    count,
    searchResponse: searchResult.content?.substring(0, 200),
    countResponse: responseText.substring(0, 500),
    searchTimeMs: searchResult.elapsedMs,
    countTimeMs: countResult.elapsedMs,
    screenshot
  };
}

async function runSC18(page) {
  console.log('\n=== SC-18: Thread Persistence ===');
  
  await page.goto(SHELL_URL);
  await waitForPageLoad(page);
  await captureEvidence(page, 'sc18_start');
  
  // Step 1: Perform search
  await sendMessage(page, 'Find marketing agencies in Brussels.');
  const searchResult = await waitForResponse(page, { maxWaitMs: 180000 });
  await captureEvidence(page, 'sc18_search_results');
  
  // Step 2: Get current URL (thread ID)
  const threadUrl = page.url();
  console.log(`[INFO] Thread URL: ${threadUrl}`);
  
  // Get messages before refresh for comparison
  const messagesBefore = await getAllMessages(page);
  console.log(`[INFO] Messages before refresh: ${messagesBefore.length}`);
  
  // Step 3: Refresh the page
  console.log('[ACTION] Refreshing page...');
  await page.reload();
  await waitForPageLoad(page);
  await captureEvidence(page, 'sc18_after_refresh');
  
  // Verify thread context persisted
  const messagesAfter = await getAllMessages(page);
  const hasContext = messagesAfter.length > 0;
  console.log(`[INFO] Messages after refresh: ${messagesAfter.length}`);
  console.log(`[VERIFY] Thread context persisted: ${hasContext ? 'YES ✓' : 'NO ✗'}`);
  
  // Step 4: Follow-up export - should reference prior search
  await sendMessage(page, 'Export that one.');
  const exportResult = await waitForResponse(page, { 
    maxWaitMs: 180000,
    waitForPattern: /export|csv|file|download/i
  });
  const screenshot = await captureEvidence(page, 'sc18_export_followup');
  
  const responseText = exportResult.content || '';
  const mentionsExport = /export|csv|file|download/i.test(responseText);
  const hasCorrectPath = responseText.includes('localhost:3000/downloads/');
  
  console.log(`[VERIFY] Response mentions export: ${mentionsExport ? 'YES ✓' : 'NO ✗'}`);
  console.log(`[VERIFY] Uses correct download path: ${hasCorrectPath ? 'YES ✓' : 'NO ✗'}`);
  console.log(`[RESPONSE] ${responseText.substring(0, 200)}...`);
  
  return {
    scenario: 'SC-18',
    persistenceWorks: mentionsExport && hasContext,
    hasContext,
    mentionsExport,
    hasCorrectPath,
    threadUrl,
    messagesBeforeCount: messagesBefore.length,
    messagesAfterCount: messagesAfter.length,
    searchResponse: searchResult.content?.substring(0, 200),
    exportResponse: responseText.substring(0, 500),
    searchTimeMs: searchResult.elapsedMs,
    exportTimeMs: exportResult.elapsedMs,
    screenshot
  };
}

async function main() {
  console.log('=== Edge CDP Scenario Runner ===');
  console.log(`Connecting to Edge at ${CDP_URL}...`);
  
  let browser;
  try {
    browser = await chromium.connectOverCDP(CDP_URL);
    console.log('[OK] Connected to Edge browser');
    
    // Create a new page for clean testing
    const context = browser.contexts()[0] || await browser.newContext();
    const page = await context.newPage();
    console.log(`[OK] Using page: ${page.url()}`);
    
    const results = {
      timestamp: new Date().toISOString(),
      cdpUrl: CDP_URL,
      shellUrl: SHELL_URL,
      sc14: null,
      sc17: null,
      sc18: null
    };
    
    // Run SC-14
    try {
      results.sc14 = await runSC14(page);
    } catch (e) {
      console.error('[ERROR] SC-14 failed:', e.message);
      await captureEvidence(page, 'sc14_error');
      results.sc14 = { error: e.message, stack: e.stack };
    }
    
    // Run SC-17
    try {
      results.sc17 = await runSC17(page);
    } catch (e) {
      console.error('[ERROR] SC-17 failed:', e.message);
      await captureEvidence(page, 'sc17_error');
      results.sc17 = { error: e.message, stack: e.stack };
    }
    
    // Run SC-18
    try {
      results.sc18 = await runSC18(page);
    } catch (e) {
      console.error('[ERROR] SC-18 failed:', e.message);
      await captureEvidence(page, 'sc18_error');
      results.sc18 = { error: e.message, stack: e.stack };
    }
    
    // Save results
    const resultsPath = path.join(SCREENSHOT_DIR, 'scenario_results.json');
    fs.writeFileSync(resultsPath, JSON.stringify(results, null, 2));
    console.log(`\n[OK] Results saved to: ${resultsPath}`);
    
    // Summary
    console.log('\n=== SUMMARY ===');
    console.log(`SC-14 (Export Path): ${results.sc14?.correctPath && results.sc14?.noStalePath ? 'PASS ✓' : 'FAIL ✗'}`);
    console.log(`  - Correct path: ${results.sc14?.correctPath ? 'YES' : 'NO'}`);
    console.log(`  - No stale path: ${results.sc14?.noStalePath ? 'YES' : 'NO'}`);
    console.log(`  - Download URL: ${results.sc14?.downloadUrl || 'N/A'}`);
    console.log(`  - Search time: ${results.sc14?.searchTimeMs || 'N/A'}ms`);
    console.log(`  - Export time: ${results.sc14?.exportTimeMs || 'N/A'}ms`);
    console.log(`SC-17 (Context Reuse): ${results.sc17?.contextReused ? 'PASS ✓' : 'FAIL ✗'}`);
    console.log(`  - Count returned: ${results.sc17?.count !== null ? results.sc17.count : 'N/A'}`);
    console.log(`  - Search time: ${results.sc17?.searchTimeMs || 'N/A'}ms`);
    console.log(`  - Count time: ${results.sc17?.countTimeMs || 'N/A'}ms`);
    console.log(`SC-18 (Persistence): ${results.sc18?.persistenceWorks ? 'PASS ✓' : 'FAIL ✗'}`);
    console.log(`  - Context persisted: ${results.sc18?.hasContext ? 'YES' : 'NO'}`);
    console.log(`  - Export followed: ${results.sc18?.mentionsExport ? 'YES' : 'NO'}`);
    console.log(`  - Correct path: ${results.sc18?.hasCorrectPath ? 'YES' : 'NO'}`);
    console.log(`  - Search time: ${results.sc18?.searchTimeMs || 'N/A'}ms`);
    console.log(`  - Export time: ${results.sc18?.exportTimeMs || 'N/A'}ms`);
    
    await browser.close();
    
  } catch (error) {
    console.error('[FATAL] Failed to connect or run scenarios:', error.message);
    if (browser) await browser.close();
    process.exit(1);
  }
}

main();
