// Supabase Configuration
// IMPORTANT: Replace these with your actual Supabase credentials from the dashboard
// Get them from: Settings → API in your Supabase project

const SUPABASE_CONFIG = {
    url: 'https://ifxgudzypalkrpabeamm.supabase.co',  // Replace with your Project URL
    anonKey: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlmeGd1ZHp5cGFsa3JwYWJlYW1tIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjAwNTQ4MTEsImV4cCI6MjA3NTYzMDgxMX0.mBnTBH0UtKZTszL_kJKhXixG_QQX9kjDfP-gWbSQiE8'  // Replace with your anon public key
};

// Initialize Supabase client and attach to window for global access
window.supabaseClient = window.supabase.createClient(SUPABASE_CONFIG.url, SUPABASE_CONFIG.anonKey);
