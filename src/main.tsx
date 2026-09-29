import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router";
import { Toaster } from "@/components/ui/toast";
import { queryClient } from "@/lib/query-client";
import { installViewportDebug } from "@/lib/viewport-debug";
import { router } from "./router";
import "./index.css";

if ((navigator as Navigator & { standalone?: boolean }).standalone === true) {
  document.documentElement.classList.add("standalone");
}
installViewportDebug();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <Toaster>
        <RouterProvider router={router} />
      </Toaster>
    </QueryClientProvider>
  </StrictMode>,
);
