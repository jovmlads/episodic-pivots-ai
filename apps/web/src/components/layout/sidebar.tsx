"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { BarChart2, Clock, Settings, Bell, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { createClient } from "@/lib/supabase/client";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: BarChart2 },
  { href: "/history", label: "History", icon: Clock },
  { href: "/settings", label: "Screener", icon: Settings },
  { href: "/notifications", label: "Notifications", icon: Bell },
];

interface Props {
  profile: { email: string; is_admin: boolean; trial_ends_at: string } | null;
}

export default function Sidebar({ profile }: Props) {
  const pathname = usePathname();
  const router = useRouter();

  async function signOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  const trialDaysLeft = profile
    ? Math.max(0, Math.ceil((new Date(profile.trial_ends_at).getTime() - Date.now()) / 86400000))
    : 0;

  return (
    <aside className="w-52 flex flex-col border-r border-border bg-background shrink-0">
      <div className="px-4 py-5 border-b border-border">
        <span className="text-sm font-bold tracking-wide">EPISODIC PIVOT</span>
      </div>

      <nav className="flex-1 px-2 py-4 space-y-1">
        {nav.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 px-3 py-2 rounded text-sm transition-colors",
              pathname === href
                ? "bg-accent text-foreground"
                : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
            )}
          >
            <Icon size={15} />
            {label}
          </Link>
        ))}
      </nav>

      <div className="px-4 py-4 border-t border-border space-y-2">
        {trialDaysLeft > 0 && (
          <p className="text-xs text-muted-foreground">
            Trial: {trialDaysLeft}d left
          </p>
        )}
        <p className="text-xs text-muted-foreground truncate">{profile?.email}</p>
        <button
          onClick={signOut}
          className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <LogOut size={13} /> Sign out
        </button>
      </div>
    </aside>
  );
}
