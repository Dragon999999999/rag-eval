/**
 * Map icon names to Lucide React components.
 *
 * This allows centralized icon configuration for navigation
 * without importing icons in multiple places.
 */
import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  Waypoints,
  Database,
  FlaskConical,
  BarChart,
  Settings,
} from "lucide-react";

export const ICONS = {
  LayoutDashboard,
  Waypoints,
  Database,
  FlaskConical,
  BarChart,
  Settings,
} as const;

export type IconName = keyof typeof ICONS;

export function getIcon(name: IconName): LucideIcon {
  return ICONS[name];
}
