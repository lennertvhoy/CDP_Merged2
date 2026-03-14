import { LineChart as LucideLineChart, BarChart2, TrendingUp, Users, DollarSign, AlertCircle, Loader2 } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { useState, useEffect } from "react";

export function InsightsView() {
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 1500);
    return () => clearTimeout(timer);
  }, []);

  const revenueData = [
    { name: 'Jan', revenue: 4000 },
    { name: 'Feb', revenue: 3000 },
    { name: 'Mar', revenue: 2000 },
    { name: 'Apr', revenue: 2780 },
    { name: 'May', revenue: 1890 },
    { name: 'Jun', revenue: 2390 },
    { name: 'Jul', revenue: 3490 },
  ];

  const segmentData = [
    { name: 'Enterprise', value: 400 },
    { name: 'Mid-Market', value: 300 },
    { name: 'SMB', value: 300 },
    { name: 'Startup', value: 200 },
  ];

  return (
    <div className="flex-1 flex flex-col bg-[#050505] overflow-hidden">
      {/* Header */}
      <div className="h-16 border-b border-zinc-800 flex items-center px-8 justify-between shrink-0 bg-zinc-950/50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-[6px] bg-purple-500/10 border border-purple-500/20 flex items-center justify-center">
            <LucideLineChart size={16} className="text-purple-400" />
          </div>
          <h1 className="text-lg font-medium text-zinc-100">Insights</h1>
        </div>
        <div className="flex items-center gap-3">
          <select className="bg-zinc-900 border border-zinc-800 rounded-[6px] py-1.5 px-3 text-sm text-zinc-100 focus:outline-none focus:border-zinc-600 appearance-none">
            <option>Last 30 Days</option>
            <option>Last 90 Days</option>
            <option>Year to Date</option>
          </select>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-6xl mx-auto flex flex-col gap-6">
          
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-32">
              <Loader2 size={32} className="text-zinc-600 animate-spin mb-4" />
              <h3 className="text-base font-medium text-zinc-300 mb-1">Loading insights...</h3>
              <p className="text-sm text-zinc-500">Crunching numbers across your segments.</p>
            </div>
          ) : (
            <>
              {/* KPI Cards */}
              <div className="grid grid-cols-4 gap-6">
                <KpiCard title="Total Revenue" value="€2.4M" trend="+12%" icon={<DollarSign size={16} />} positive />
                <KpiCard title="Active Segments" value="14" trend="+2" icon={<Users size={16} />} positive />
                <KpiCard title="Avg. Health Score" value="84" trend="-3%" icon={<TrendingUp size={16} />} positive={false} />
                <KpiCard title="Revenue at Risk" value="€120k" trend="+15%" icon={<AlertCircle size={16} />} positive={false} />
              </div>

              {/* Charts */}
              <div className="grid grid-cols-2 gap-6">
                <div className="bg-[#0a0a0a] border border-zinc-800 rounded-xl p-6 flex flex-col gap-6">
                  <div className="flex flex-col gap-1">
                    <h3 className="text-sm font-medium text-zinc-200">Revenue Trend</h3>
                    <span className="text-xs text-zinc-500">Monthly recurring revenue across all segments.</span>
                  </div>
                  <div className="h-64 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={revenueData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                        <XAxis dataKey="name" stroke="#71717a" fontSize={12} tickLine={false} axisLine={false} />
                        <YAxis stroke="#71717a" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(value) => `€${value/1000}k`} />
                        <Tooltip 
                          contentStyle={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px' }}
                          itemStyle={{ color: '#e4e4e7' }}
                        />
                        <Line type="monotone" dataKey="revenue" stroke="#a855f7" strokeWidth={2} dot={{ fill: '#a855f7', strokeWidth: 2, r: 4 }} activeDot={{ r: 6 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                <div className="bg-[#0a0a0a] border border-zinc-800 rounded-xl p-6 flex flex-col gap-6">
                  <div className="flex flex-col gap-1">
                    <h3 className="text-sm font-medium text-zinc-200">Segment Distribution</h3>
                    <span className="text-xs text-zinc-500">Active companies by primary segment.</span>
                  </div>
                  <div className="h-64 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={segmentData} layout="vertical" margin={{ top: 0, right: 0, left: 20, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" horizontal={false} />
                        <XAxis type="number" stroke="#71717a" fontSize={12} tickLine={false} axisLine={false} />
                        <YAxis dataKey="name" type="category" stroke="#71717a" fontSize={12} tickLine={false} axisLine={false} />
                        <Tooltip 
                          contentStyle={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px' }}
                          itemStyle={{ color: '#e4e4e7' }}
                          cursor={{ fill: '#27272a', opacity: 0.4 }}
                        />
                        <Bar dataKey="value" fill="#3b82f6" radius={[0, 4, 4, 0]} barSize={24} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            </>
          )}

        </div>
      </div>
    </div>
  );
}

function KpiCard({ title, value, trend, icon, positive }: { title: string, value: string, trend: string, icon: React.ReactNode, positive: boolean }) {
  return (
    <div className="bg-[#0a0a0a] border border-zinc-800 rounded-xl p-5 flex flex-col gap-4 hover:border-zinc-700 transition-colors">
      <div className="flex items-center justify-between text-zinc-400">
        <span className="text-sm font-medium">{title}</span>
        {icon}
      </div>
      <div className="flex items-end justify-between">
        <span className="text-2xl font-semibold text-zinc-100">{value}</span>
        <span className={`text-xs font-medium px-2 py-1 rounded-[4px] ${
          positive ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'
        }`}>
          {trend}
        </span>
      </div>
    </div>
  );
}
