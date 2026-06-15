export default function DashboardHome() {
  return (
    <div className="animate-in">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Welcome to GoMarg</h1>
        <p className="text-muted-foreground">Here is an overview of your sales engine.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {[
          { label: 'Total Leads', value: '1,234', trend: '+12% this week' },
          { label: 'Active Campaigns', value: '5', trend: '2 starting soon' },
          { label: 'Emails Sent', value: '8,432', trend: '+24% this week' },
        ].map((stat, i) => (
          <div key={i} className="glass p-6 rounded-2xl hover:border-blue-500/30 transition-all duration-300">
            <p className="text-muted-foreground font-medium mb-2">{stat.label}</p>
            <h3 className="text-4xl font-bold mb-2">{stat.value}</h3>
            <p className="text-sm text-blue-400">{stat.trend}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
