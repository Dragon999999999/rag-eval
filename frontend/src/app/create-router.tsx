import { createBrowserRouter, type RouteObject } from "react-router-dom";
import { AppLayout } from "@/components/layout/app-layout";
import { DesignSystemShowcase } from "@/app/design-system/showcase";

const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppLayout />,
    children: [
      {
        index: true,
        element: (
          <div className="p-6 text-text-secondary">RAG-Eval Dashboard (TODO)</div>
        ),
      },
      {
        path: "design-system",
        element: <DesignSystemShowcase />,
      },
    ],
  },
];

export function createRouter() {
  return createBrowserRouter(routes);
}
