import { ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { useSidebarStore } from "~/stores/sidebarStore";

interface LayoutProps {
  children: ReactNode;
  /** 是否显示侧边栏，默认 true */
  showSidebar?: boolean;
}

export function Layout({ children, showSidebar = true }: LayoutProps) {
  const { isOpen } = useSidebarStore();

  if (!showSidebar) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-base-100">
      <Sidebar />
      <main
        className={`min-h-screen transition-all duration-300 ease-in-out ${
          isOpen ? "ml-72" : "ml-0"
        }`}
      >
        {children}
      </main>
    </div>
  );
}
