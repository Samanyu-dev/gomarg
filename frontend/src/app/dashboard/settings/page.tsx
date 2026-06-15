export default function SettingsPage() {
  return (
    <div className="animate-in">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Settings</h1>
        <p className="text-muted-foreground">Manage your account and integration preferences.</p>
      </div>

      <div className="glass p-8 rounded-2xl border border-white/5 max-w-2xl">
        <div className="space-y-6">
          <div>
            <h3 className="text-lg font-semibold mb-1">Apollo Integration</h3>
            <p className="text-sm text-muted-foreground mb-4">Connect your Apollo account to sync leads seamlessly.</p>
            <div className="flex items-center gap-4 p-4 bg-black/20 rounded-xl border border-white/5">
              <div className="w-3 h-3 rounded-full bg-green-500 shadow-[0_0_10px_rgba(34,197,94,0.5)]"></div>
              <div>
                <p className="font-medium">Apollo Connected</p>
                <p className="text-xs text-muted-foreground">API Key active and verified</p>
              </div>
            </div>
          </div>

          <hr className="border-white/10" />

          <div>
            <h3 className="text-lg font-semibold mb-1">AI Language Model</h3>
            <p className="text-sm text-muted-foreground mb-4">Configure your LLM provider for email generation.</p>
            <div className="flex items-center gap-4 p-4 bg-black/20 rounded-xl border border-white/5">
              <div className="w-3 h-3 rounded-full bg-green-500 shadow-[0_0_10px_rgba(34,197,94,0.5)]"></div>
              <div>
                <p className="font-medium">Gemini 2.5 Flash</p>
                <p className="text-xs text-muted-foreground">Using default system API Key</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
