import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useLocation } from "react-router-dom";
import { api, type Org } from "./api";

type OrgBrandingContextValue = {
  headerName: string;
  /** Full URL for the header banner `<img src=…>` (includes cache-bust when the file is replaced). */
  bannerSrc: string | null;
  /** Apply fresh org data to the shell (pass `Org` from a mutation response to avoid an extra GET). */
  refreshOrgBranding: (updated?: Org) => Promise<void>;
};

const OrgBrandingContext = createContext<OrgBrandingContextValue | null>(null);

export function OrgBrandingProvider({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [headerName, setHeaderName] = useState("");
  const [bannerKey, setBannerKey] = useState<string | null>(null);
  const [bannerVersion, setBannerVersion] = useState(0);

  const applyOrg = useCallback((o: Org) => {
    setHeaderName((o.header_display_name || "").trim());
    setBannerKey(o.banner_file_key);
    setBannerVersion((v) => v + 1);
  }, []);

  const refreshOrgBranding = useCallback(
    async (updated?: Org) => {
      if (updated) {
        applyOrg(updated);
        return;
      }
      try {
        const fetched = await api.getOrg();
        applyOrg(fetched);
      } catch {
        setHeaderName("");
        setBannerKey(null);
        setBannerVersion((v) => v + 1);
      }
    },
    [applyOrg]
  );

  useEffect(() => {
    void refreshOrgBranding();
  }, [location.pathname, refreshOrgBranding]);

  const bannerSrc = useMemo(() => {
    if (!bannerKey) return null;
    const base = api.fileUrl(bannerKey);
    const sep = base.includes("?") ? "&" : "?";
    return `${base}${sep}cb=${bannerVersion}`;
  }, [bannerKey, bannerVersion]);

  const value = useMemo<OrgBrandingContextValue>(
    () => ({
      headerName,
      bannerSrc,
      refreshOrgBranding,
    }),
    [headerName, bannerSrc, refreshOrgBranding]
  );

  return <OrgBrandingContext.Provider value={value}>{children}</OrgBrandingContext.Provider>;
}

export function useOrgBranding(): OrgBrandingContextValue {
  const ctx = useContext(OrgBrandingContext);
  if (!ctx) {
    throw new Error("useOrgBranding must be used within OrgBrandingProvider");
  }
  return ctx;
}
