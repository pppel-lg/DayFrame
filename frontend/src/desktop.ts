type NativeBridge = {
  invoke<T>(command: string, args?: Record<string, unknown>): Promise<T>;
};
declare global {
  interface Window {
    __TAURI_INTERNALS__?: NativeBridge;
  }
}

export const isDesktop = () =>
  typeof window !== "undefined" && !!window.__TAURI_INTERNALS__;
export async function chooseDirectory(): Promise<string | null> {
  const bridge = window.__TAURI_INTERNALS__;
  if (!bridge) throw new Error("请选择桌面应用中的目录设置。");
  return bridge.invoke<string | null>("choose_directory");
}
export async function restartDesktop(): Promise<void> {
  const bridge = window.__TAURI_INTERNALS__;
  if (!bridge) throw new Error("请在桌面应用中重新启动。");
  await bridge.invoke("restart_desktop");
}
export type DesktopStatus = {
  desktop: true;
  paths: { archive: string; backups: string };
  pending_restart: boolean;
};
