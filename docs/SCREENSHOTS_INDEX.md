# Screenshot Documentation Index

**Generated:** 2026-03-07  
**Purpose:** Central repository of screenshots for documentation and demo creation

---

## Chatbot Testing Screenshots

### New Screenshots from This Session (2026-03-07)

| Screenshot | Description | Use Case |
|------------|-------------|----------|
| `chatbot_initial_load_2026-03-07.png` | Initial chatbot landing page showing "Belgian customer intelligence" | Demo intro, product overview |
| `chatbot_test1_restaurants_gent_thinking.png` | Query "How many restaurant companies are in Gent?" with AI thinking | Multi-turn conversation demo |
| `chatbot_test2_segment_creation.png` | Creating "Gent Restaurants" segment with 1,105 companies | Segment creation feature |
| `chatbot_test3_export_csv.png` | Export options for CSV with field selection | Data export feature |
| `chatbot_test4_artifact_created.png` | Artifact created with download link | Artifact generation feature |
| `chatbot_test5_analytics_brussels.png` | Analytics: Top industries in Brussels (41,290 companies) | Analytics/aggregation demo |

### Previous Chatbot Screenshots

| Screenshot | Description | Use Case |
|------------|-------------|----------|
| `chatbot_full_flow_test_2026-03-07.png` | Full multi-turn conversation flow | End-to-end demo |
| `chatbot_test1_gent_restaurants.png` | Gent restaurants query result | Basic search demo |
| `chatbot_test1_gent_restaurants_result.png` | Result showing 1,105 restaurants | Count accuracy demo |
| `chatbot_test1_gent_restaurants_final.png` | Final result with suggestions | UX flow demo |
| `chatbot_local_openai_success.png` | Local OpenAI integration working | Technical setup demo |
| `chatbot_action_success.png` | Action execution success | Tool execution demo |
| `chatbot_response_success.png` | Successful chatbot response | Response quality demo |
| `chatbot_quality_matrix_eval_2026-03-06.png` | Quality matrix evaluation | Testing/QA documentation |
| `chatbot_rate_limit_fix_verified.png` | Rate limit fix verification | Performance documentation |
| `chatbot_restaurants_eval_2026-03-06.png` | Restaurant evaluation results | Feature testing |

---

## Tracardi GUI Screenshots

### Dashboard & Overview

| Screenshot | Description | Use Case |
|------------|-------------|----------|
| `tracardi_dashboard_2026-03-07.png` | Main Tracardi dashboard (64 events, 43 profiles) | Platform overview |
| `tracardi_dashboard_verified_2026-03-07.png` | Verified dashboard state | System health demo |
| `tracardi_dashboard_2500_profiles.png` | Dashboard with 2500 profiles | Scale demonstration |
| `tracardi_dashboard_final_2500.png` | Final 2500 profiles view | Scale documentation |
| `tracardi_login_initial.png` | Login page | Authentication flow |
| `tracardi_login_test.png` | Login test | Setup documentation |

### Event Sources

| Screenshot | Description | Use Case |
|------------|-------------|----------|
| `tracardi_event_sources_2026-03-07.png` | All 4 event sources configured and active | Integration setup |
| `tracardi_event_sources_verified.png` | Event sources verification | System verification |
| `tracardi_event_sources_test.png` | Event sources test view | Testing documentation |
| `tracardi_event_sources_list.png` | List of event sources | Configuration reference |
| `tracardi_event_sources_list_test.png` | Event sources list test | QA documentation |

### Workflows

| Screenshot | Description | Use Case |
|------------|-------------|----------|
| `tracardi_workflows_list_2026-03-07.png` | All 5 email processing workflows listed | Automation overview |
| `tracardi_workflows_configured.png` | Workflows configured state | Setup completion |
| `tracardi_workflows_created.png` | Workflows created view | Configuration demo |
| `tracardi_workflow_bounce_processor_2026-03-07.png` | Email Bounce Processor workflow diagram | Workflow detail |
| `tracardi_workflow_email_bounce_deployed.png` | Deployed email bounce workflow | Deployment verification |
| `tracardi_workflow_editor.png` | Workflow editor interface | Editor feature demo |
| `tracardi_flow_editor_email_bounce.png` | Flow editor for email bounce | Editor detail |
| `tracardi_workflows_empty.png` | Empty workflows state (before setup) | Before/after comparison |

### Profiles & Data

| Screenshot | Description | Use Case |
|------------|-------------|----------|
| `tracardi_gui_profile_search_working.png` | Profile search functionality | Search feature demo |
| `tracardi_profiles_list_test.png` | Profiles list view | Data management demo |
| `tracardi_profile_detail_test.png` | Profile detail view | 360-view feature |
| `tracardi_profiles_error.png` | Profile error state | Troubleshooting doc |

### Email Integration

| Screenshot | Description | Use Case |
|------------|-------------|----------|
| `tracardi_resend_setup_complete.png` | Resend integration complete | Integration setup |
| `tracardi_resend_webhook_detail_test.png` | Resend webhook details | Technical configuration |

---

## Analytics Screenshots

| Screenshot | Description | Use Case |
|------------|-------------|----------|
| `analytics_test_brussels_timeout_2026-03-06.png` | Brussels analytics test | Performance testing |
| `analytics_test_initial.png` | Initial analytics test | Testing baseline |
| `analytics_test_resized.png` | Resized analytics view | UI testing |
| `analytics_test_result.png` | Analytics test results | Results documentation |
| `analytics_test_top_industries.png` | Top industries analysis | Analytics feature demo |

---

## Infrastructure & Testing

| Screenshot | Description | Use Case |
|------------|-------------|----------|
| `bridge_test_tracardi_dashboard.png` | Bridge test dashboard | Integration testing |
| `chatbot_initial_state.png` | Initial chatbot state | Setup documentation |
| `chatbot_final_verification.png` | Final verification state | QA completion |
| `chatbot_final_verification_success.png` | Successful final verification | Success documentation |
| `tracardi_recovery_success_2026-03-03.png` | Recovery success | Disaster recovery doc |
| `tracardi_stable_after_fixes_2026-03-03.png` | System stability post-fixes | Maintenance documentation |

---

## Recommended Screenshot Sequences for Demo

### 1. End-to-End User Journey
1. `chatbot_initial_load_2026-03-07.png` - Landing page
2. `chatbot_test1_restaurants_gent_thinking.png` - Search query
3. `chatbot_test2_segment_creation.png` - Segment creation
4. `chatbot_test4_artifact_created.png` - Export artifact
5. `chatbot_test5_analytics_brussels.png` - Analytics

### 2. Platform Architecture
1. `tracardi_dashboard_2026-03-07.png` - Tracardi dashboard
2. `tracardi_event_sources_2026-03-07.png` - Event sources
3. `tracardi_workflows_list_2026-03-07.png` - Automation workflows
4. `tracardi_workflow_bounce_processor_2026-03-07.png` - Workflow detail

### 3. Setup & Configuration
1. `tracardi_login_initial.png` - Login
2. `tracardi_event_sources_verified.png` - Event sources
3. `tracardi_workflows_configured.png` - Workflows
4. `tracardi_resend_setup_complete.png` - Email integration

---

## Technical Notes

- All screenshots are PNG format with high resolution (1440x900 viewport)
- Screenshots are stored in repository root for easy access
- New screenshots from this session use `*_2026-03-07.png` naming convention
- Browser testing was performed using Playwright automation
- Services verified: Chatbot (localhost:8000), Tracardi GUI (localhost:8787)

---

**Total Screenshots Available:** 61
**Screenshots from This Session:** 11 new screenshots added
**Recommended for Demo:** 15-20 key screenshots
