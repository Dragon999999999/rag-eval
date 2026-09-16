import { NavLink } from "react-router-dom";

const navigation = [
  { name: "Dashboard", href: "/" },
  { name: "Design System", href: "/design-system" },
];

export function Sidebar() {
  return (
    <aside className="w-56 border-r border-border-default bg-surface p-4">
      <nav className="space-y-1">
        {navigation.map((item) => (
          <NavLink
            key={item.name}
            to={item.href}
            className={({ isActive }) =>
              [
                "block rounded-md px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-surface-active text-text-primary"
                  : "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
              ].join(" ")
            }
          >
            {item.name}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
