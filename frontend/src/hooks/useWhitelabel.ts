import { useQuery } from "@tanstack/react-query";
import api from "../api/client";

export type WhiteLabelData = {
  brand_name?: string | null;
  logo_url?: string | null;
  primary_color?: string | null;
  favicon_url?: string | null;
};

export function useWhitelabel() {
  const { data } = useQuery({
    queryKey: ["settings", "whitelabel"],
    queryFn: () => api.get<WhiteLabelData>("/settings/whitelabel").then((r) => r.data),
    staleTime: 60_000,
  });
  return {
    brandName: data?.brand_name || "Dorvey",
    logoUrl: data?.logo_url || null,
    primaryColor: data?.primary_color || "#10b981", // emerald-500
    faviconUrl: data?.favicon_url || null,
  };
}
