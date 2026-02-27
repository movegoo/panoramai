"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  MapPin, Users, Home, TrendingUp, Settings, Search, Car, Train, Bike,
  Layers, Zap, Coffee, ShoppingBag, Building2, GraduationCap, ChevronDown,
  ChevronUp, RefreshCw, Briefcase, Euro, PieChart, UserCheck, Target,
  Sparkles, ArrowRight, MousePointer, Navigation, Info, Store, Smartphone
} from "lucide-react";

// =============================================================================
// Types
// =============================================================================

interface MobiliteStats {
  communes_couvertes: number;
  pct_voiture: number;
  pct_transport_commun: number;
  pct_velo_2roues: number;
  pct_marche: number;
}

interface SocioDemoStats {
  communes_couvertes: number;
  genre: { hommes: number; femmes: number; pct_hommes: number; pct_femmes: number } | null;
  tranches_age: Record<string, number> | null;
  taux_chomage: number | null;
  pct_proprietaires: number | null;
  revenu_median: number | null;
  taux_pauvrete: number | null;
  taux_mobinautes: number | null;
  csp: Record<string, number> | null;
}

interface ZoneAnalysis {
  center: { latitude: number; longitude: number };
  radius_km: number;
  analysis: {
    population_totale: number;
    superficie_totale_km2: number | null;
    densite_moyenne: number | null;
    nb_communes: number;
    loyer_moyen_m2_appartement: number | null;
    loyer_moyen_m2_maison: number | null;
    mobilite: MobiliteStats | null;
    socio_demo: SocioDemoStats | null;
  };
  communes: Array<{
    code: string;
    nom_commune: string;
    population: number;
    latitude: number;
    longitude: number;
    distance_km: number;
    loyer_m2_appartement?: number;
  }>;
}

interface IrisFeature {
  iris_code: string;
  iris_name: string;
  com_code: string;
  com_name: string;
  geo_shape: {
    type: string;
    geometry: {
      type: string;
      coordinates: number[][][];
    };
  };
}

interface Store {
  id: number;
  name: string;
  city: string;
  latitude: number;
  longitude: number;
  store_type?: string;
  google_rating?: number;
  google_reviews_count?: number;
  postal_code?: string;
}

interface LayerConfig {
  id: string;
  name: string;
  icon: React.ReactNode;
  color: string;
  enabled: boolean;
  loading?: boolean;
  description?: string;
}

interface IRVEStation {
  id: string;
  nom: string;
  adresse: string;
  commune: string;
  latitude: number;
  longitude: number;
  nb_points_charge: number;
  puissance_max_kw: number;
  operateur: string;
  gratuit: boolean;
}

interface POI {
  id: number;
  name: string;
  category: string;
  latitude: number;
  longitude: number;
}

interface CompetitorStoreGroup {
  competitor_id: number;
  competitor_name: string;
  color: string;
  logo_url?: string;
  total: number;
  avg_rating?: number;
  total_reviews?: number;
  stores_with_rating?: number;
  stores: Array<{
    id: number;
    name: string;
    brand_name: string;
    category: string;
    city: string;
    postal_code: string;
    latitude: number;
    longitude: number;
    google_rating?: number;
    google_reviews_count?: number;
  }>;
}

interface QuickLocation {
  name: string;
  lat: number;
  lng: number;
  emoji: string;
  description: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

function authHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const headers: Record<string, string> = {};
  const token = localStorage.getItem("auth_token");
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const advId = localStorage.getItem("current_advertiser_id");
  if (advId) headers["X-Advertiser-Id"] = advId;
  return headers;
}

type AnalysisMode = "radius" | "postal_code" | "iris";

// Quick access locations for empty state
const QUICK_LOCATIONS: QuickLocation[] = [
  { name: "Paris", lat: 48.8566, lng: 2.3522, emoji: "🗼", description: "Capitale" },
  { name: "Lyon", lat: 45.7640, lng: 4.8357, emoji: "🦁", description: "Rhône-Alpes" },
  { name: "Marseille", lat: 43.2965, lng: 5.3698, emoji: "⚓", description: "Méditerranée" },
  { name: "Bordeaux", lat: 44.8378, lng: -0.5792, emoji: "🍷", description: "Nouvelle-Aquitaine" },
  { name: "Lille", lat: 50.6292, lng: 3.0573, emoji: "🏭", description: "Hauts-de-France" },
  { name: "Nantes", lat: 47.2184, lng: -1.5536, emoji: "🚢", description: "Pays de la Loire" },
];

// =============================================================================
// Component
// =============================================================================

export default function FranceMap() {
  // Refs
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const circleRef = useRef<any>(null);
  const leafletRef = useRef<any>(null);
  const irisLayerRef = useRef<any>(null);
  const irisDataRef = useRef<Map<string, IrisFeature>>(new Map());
  const layerGroupsRef = useRef<Map<string, any>>(new Map());

  // State
  const [stores, setStores] = useState<Store[]>([]);
  const [zoneAnalysis, setZoneAnalysis] = useState<ZoneAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [mapReady, setMapReady] = useState(false);

  // Analysis settings
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>("radius");
  const [radius, setRadius] = useState(15);
  const [postalCode, setPostalCode] = useState("");
  const [searchLoading, setSearchLoading] = useState(false);

  // IRIS
  const [showIrisLayer, setShowIrisLayer] = useState(false);
  const [irisLoading, setIrisLoading] = useState(false);
  const [selectedIris, setSelectedIris] = useState<IrisFeature | null>(null);

  // Layers panel
  const [layersPanelOpen, setLayersPanelOpen] = useState(false);
  const [layers, setLayers] = useState<LayerConfig[]>([
    { id: "competitor_stores", name: "Magasins concurrents", icon: <Store className="h-4 w-4" />, color: "#ef4444", enabled: true, description: "Base nationale des commerces" },
    { id: "catchment_zones", name: "Zones de chalandise", icon: <Target className="h-4 w-4" />, color: "#8b5cf6", enabled: false, description: "Couverture population" },
    { id: "irve", name: "Bornes électriques", icon: <Zap className="h-4 w-4" />, color: "#22c55e", enabled: false, description: "200k+ bornes IRVE" },
    { id: "poi_restaurant", name: "Restaurants", icon: <Coffee className="h-4 w-4" />, color: "#f59e0b", enabled: false, description: "Via OpenStreetMap" },
    { id: "poi_shop", name: "Commerces", icon: <ShoppingBag className="h-4 w-4" />, color: "#ec4899", enabled: false, description: "Via OpenStreetMap" },
    { id: "regions", name: "Régions", icon: <MapPin className="h-4 w-4" />, color: "#8b5cf6", enabled: false, description: "geo.api.gouv.fr" },
    { id: "departements", name: "Départements", icon: <Building2 className="h-4 w-4" />, color: "#3b82f6", enabled: false, description: "geo.api.gouv.fr" },
    { id: "communes", name: "Communes", icon: <Home className="h-4 w-4" />, color: "#6366f1", enabled: false, description: "35k communes (lourd)" },
    { id: "academies", name: "Académies", icon: <GraduationCap className="h-4 w-4" />, color: "#14b8a6", enabled: false, description: "Zones scolaires" },
  ]);

  // Layer data
  const [irveStations, setIrveStations] = useState<IRVEStation[]>([]);
  const [pois, setPois] = useState<POI[]>([]);
  const [irveStats, setIrveStats] = useState<any>(null);
  const [competitorStoreGroups, setCompetitorStoreGroups] = useState<CompetitorStoreGroup[]>([]);
  const [gmbEnriching, setGmbEnriching] = useState(false);

  // Catchment zones
  const [catchmentData, setCatchmentData] = useState<any>(null);
  const [catchmentRadius, setCatchmentRadius] = useState(10);
  const catchmentRadiusRef = useRef(10);

  // Active tab for analysis panel
  const [activeTab, setActiveTab] = useState<"overview" | "demo" | "communes">("overview");

  // Centre de la France
  const defaultCenter: [number, number] = [46.603354, 1.888334];
  const defaultZoom = 6;

  // =========================================================================
  // Map initialization
  // =========================================================================

  useEffect(() => {
    const timer = setTimeout(() => {
      initMap();
      loadStores();
    }, 100);

    return () => {
      clearTimeout(timer);
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  const initMap = async () => {
    if (typeof window === "undefined" || !mapRef.current) return;
    if (mapInstanceRef.current) return;

    const L = (await import("leaflet")).default;
    // MarkerCluster plugin for clustering thousands of store markers
    await import("leaflet.markercluster");

    // @ts-ignore
    delete L.Icon.Default.prototype._getIconUrl;
    L.Icon.Default.mergeOptions({
      iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
      iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
      shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
    });

    const map = L.map(mapRef.current).setView(defaultCenter, defaultZoom);

    // Use a nicer tile layer
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
      maxZoom: 19,
    }).addTo(map);

    mapInstanceRef.current = map;
    leafletRef.current = L;

    map.on("click", (e: any) => {
      handleMapClick(e.latlng.lat, e.latlng.lng);
    });

    setMapReady(true);
  };

  // =========================================================================
  // Store markers
  // =========================================================================

  const loadStores = async () => {
    try {
      const res = await fetch(`${API_BASE}/geo/stores`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setStores(data);
        setTimeout(() => addStoreMarkers(data), 500);
      }
    } catch (err) {
      console.error("Failed to load stores:", err);
    }
  };

  const addStoreMarkers = async (storeList: Store[]) => {
    if (!mapInstanceRef.current) return;

    const L = (await import("leaflet")).default;
    const map = mapInstanceRef.current;

    const blueIcon = new L.Icon({
      iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png",
      shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
      iconSize: [25, 41],
      iconAnchor: [12, 41],
      popupAnchor: [1, -34],
      shadowSize: [41, 41],
    });

    storeList.forEach((store) => {
      if (store.latitude && store.longitude) {
        let popupHtml = `<b>${store.name}</b><br>${store.city}${store.postal_code ? ` (${store.postal_code})` : ''}`;
        if (store.google_rating != null) {
          popupHtml += `<br><span style="font-size:13px">⭐ <b>${store.google_rating}</b>/5</span>`;
          if (store.google_reviews_count != null) {
            popupHtml += ` <span style="color:#666;font-size:12px">(${store.google_reviews_count.toLocaleString()} avis)</span>`;
          }
        }
        L.marker([store.latitude, store.longitude], { icon: blueIcon })
          .addTo(map)
          .bindPopup(popupHtml);
      }
    });
  };

  // =========================================================================
  // Zone analysis
  // =========================================================================

  const handleMapClick = async (lat: number, lng: number) => {
    if (analysisMode !== "radius") return;
    await analyzeByRadius(lat, lng, radius);
  };

  const analyzeByRadius = async (lat: number, lng: number, radiusKm: number) => {
    const map = mapInstanceRef.current;
    const L = leafletRef.current;
    if (!map || !L) return;

    setLoading(true);

    if (circleRef.current) {
      map.removeLayer(circleRef.current);
    }

    circleRef.current = L.circle([lat, lng], {
      radius: radiusKm * 1000,
      color: "#6366f1",
      fillColor: "#6366f1",
      fillOpacity: 0.12,
      weight: 2,
    }).addTo(map);

    map.setView([lat, lng], Math.max(10, 14 - Math.log2(radiusKm)));

    try {
      const res = await fetch(`${API_BASE}/geo/zone/analyze-enriched`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          latitude: lat,
          longitude: lng,
          radius_km: radiusKm,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setZoneAnalysis(data);
        setActiveTab("overview");
        loadLayersForArea(lat, lng, radiusKm);
      }
    } catch (err) {
      console.error("Failed to analyze zone:", err);
    } finally {
      setLoading(false);
    }
  };

  const analyzeByPostalCode = async () => {
    if (!postalCode || postalCode.length !== 5) return;

    setSearchLoading(true);
    const map = mapInstanceRef.current;
    const L = leafletRef.current;

    try {
      const geoRes = await fetch(
        `https://geo.api.gouv.fr/communes?codePostal=${postalCode}&fields=centre,nom,population,codesPostaux&format=json`
      );

      if (!geoRes.ok) {
        alert("Code postal non trouvé");
        return;
      }

      const communes = await geoRes.json();
      if (communes.length === 0) {
        alert("Code postal non trouvé");
        return;
      }

      const commune = communes[0];
      const lat = commune.centre?.coordinates[1];
      const lng = commune.centre?.coordinates[0];

      if (!lat || !lng) {
        alert("Coordonnées non disponibles");
        return;
      }

      if (circleRef.current && map) {
        map.removeLayer(circleRef.current);
      }

      if (map && L) {
        circleRef.current = L.circle([lat, lng], {
          radius: 5000,
          color: "#10b981",
          fillColor: "#10b981",
          fillOpacity: 0.12,
          weight: 2,
        }).addTo(map);

        map.setView([lat, lng], 12);
      }

      const res = await fetch(`${API_BASE}/geo/zone/analyze-enriched`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          latitude: lat,
          longitude: lng,
          radius_km: 5,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        data.postal_code = postalCode;
        data.commune_name = commune.nom;
        setZoneAnalysis(data);
        setActiveTab("overview");
        loadLayersForArea(lat, lng, 5);
      }
    } catch (err) {
      console.error("Failed to analyze postal code:", err);
      alert("Erreur lors de l'analyse");
    } finally {
      setSearchLoading(false);
    }
  };

  // Quick location analysis
  const analyzeQuickLocation = (location: QuickLocation) => {
    analyzeByRadius(location.lat, location.lng, 10);
  };

  // =========================================================================
  // IRIS layer
  // =========================================================================

  const loadIrisForBounds = useCallback(async () => {
    const map = mapInstanceRef.current;
    const L = leafletRef.current;
    if (!map || !L) return;

    const zoom = map.getZoom();
    if (zoom < 10) {
      if (irisLayerRef.current) {
        map.removeLayer(irisLayerRef.current);
        irisLayerRef.current = null;
      }
      return;
    }

    setIrisLoading(true);
    const bounds = map.getBounds();
    const ne = bounds.getNorthEast();
    const sw = bounds.getSouthWest();

    try {
      const url = `https://public.opendatasoft.com/api/explore/v2.1/catalog/datasets/georef-france-iris/records?limit=100&select=iris_code,iris_name,com_code,com_name,geo_shape&where=within_distance(geo_point_2d,geom'POINT(${(ne.lng + sw.lng) / 2} ${(ne.lat + sw.lat) / 2})',${Math.max((ne.lat - sw.lat) * 111, 20)}km)`;

      const res = await fetch(url);
      if (!res.ok) return;

      const data = await res.json();

      if (irisLayerRef.current) {
        map.removeLayer(irisLayerRef.current);
      }

      const features = data.results
        .filter((r: any) => r.geo_shape)
        .map((r: any) => {
          irisDataRef.current.set(r.iris_code, r);
          return {
            type: "Feature",
            properties: {
              iris_code: r.iris_code,
              iris_name: r.iris_name,
              com_name: r.com_name,
            },
            geometry: r.geo_shape.geometry,
          };
        });

      if (features.length === 0) {
        setIrisLoading(false);
        return;
      }

      irisLayerRef.current = L.geoJSON(
        { type: "FeatureCollection", features },
        {
          style: (feature: any) => ({
            color: selectedIris?.iris_code === feature.properties.iris_code ? "#ef4444" : "#6366f1",
            weight: selectedIris?.iris_code === feature.properties.iris_code ? 3 : 1,
            fillColor: "#6366f1",
            fillOpacity: 0.1,
          }),
          onEachFeature: (feature: any, layer: any) => {
            layer.on({
              click: () => {
                const irisData = irisDataRef.current.get(feature.properties.iris_code);
                if (irisData) {
                  setSelectedIris(irisData);
                  analyzeIris(irisData);
                }
              },
              mouseover: (e: any) => {
                e.target.setStyle({ fillOpacity: 0.3, weight: 2 });
              },
              mouseout: (e: any) => {
                e.target.setStyle({
                  fillOpacity: 0.1,
                  weight: selectedIris?.iris_code === feature.properties.iris_code ? 3 : 1,
                });
              },
            });
            layer.bindTooltip(`${feature.properties.iris_name}<br/>${feature.properties.com_name}`, {
              sticky: true,
            });
          },
        }
      ).addTo(map);
    } catch (err) {
      console.error("Failed to load IRIS:", err);
    } finally {
      setIrisLoading(false);
    }
  }, [selectedIris]);

  const analyzeIris = async (iris: IrisFeature) => {
    setLoading(true);
    try {
      const coords = iris.geo_shape.geometry.coordinates[0];
      let sumLat = 0, sumLng = 0;
      coords.forEach((c: number[]) => {
        sumLng += c[0];
        sumLat += c[1];
      });
      const centerLat = sumLat / coords.length;
      const centerLng = sumLng / coords.length;

      const res = await fetch(`${API_BASE}/geo/zone/analyze-enriched`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          latitude: centerLat,
          longitude: centerLng,
          radius_km: 1,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        data.iris_code = iris.iris_code;
        data.iris_name = iris.iris_name;
        data.commune_name = iris.com_name;
        setZoneAnalysis(data);
        setActiveTab("overview");
      }
    } catch (err) {
      console.error("Failed to analyze IRIS:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !mapReady) return;

    if (showIrisLayer) {
      loadIrisForBounds();
      map.on("moveend", loadIrisForBounds);
    } else {
      if (irisLayerRef.current) {
        map.removeLayer(irisLayerRef.current);
        irisLayerRef.current = null;
      }
      map.off("moveend", loadIrisForBounds);
    }

    return () => {
      map.off("moveend", loadIrisForBounds);
    };
  }, [showIrisLayer, mapReady, loadIrisForBounds]);

  // Auto-load competitor stores + brand stores when map is ready
  useEffect(() => {
    if (!mapReady || !mapInstanceRef.current || !leafletRef.current) return;
    const map = mapInstanceRef.current;
    const L = leafletRef.current;

    // Load brand stores
    loadStores();

    // Load competitor stores if layer is enabled by default
    const compLayer = layers.find(l => l.id === "competitor_stores");
    if (compLayer?.enabled && !layerGroupsRef.current.has("competitor_stores")) {
      setLayers(prev => prev.map(l =>
        l.id === "competitor_stores" ? { ...l, loading: true } : l
      ));
      loadCompetitorStoresLayer(map, L).then(() => {
        setLayers(prev => prev.map(l =>
          l.id === "competitor_stores" ? { ...l, loading: false } : l
        ));
      }).catch(() => {
        setLayers(prev => prev.map(l =>
          l.id === "competitor_stores" ? { ...l, loading: false } : l
        ));
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapReady]);

  // =========================================================================
  // Layer management
  // =========================================================================

  const toggleLayer = async (layerId: string) => {
    const layer = layers.find(l => l.id === layerId);
    if (!layer) return;

    const map = mapInstanceRef.current;
    const L = leafletRef.current;
    if (!map || !L) return;

    const isCurrentlyEnabled = layer.enabled;

    if (isCurrentlyEnabled) {
      const layerGroup = layerGroupsRef.current.get(layerId);
      if (layerGroup) {
        map.removeLayer(layerGroup);
        layerGroupsRef.current.delete(layerId);
      }
      // Clean up move handlers
      if (layerId === "competitor_stores") {
        const handler = (layerGroupsRef.current as any).__competitorMoveHandler;
        if (handler) map.off("moveend", handler);
      }
      if (layerId === "catchment_zones") {
        const handler = (layerGroupsRef.current as any).__catchmentMoveHandler;
        if (handler) map.off("moveend", handler);
        setCatchmentData(null);
      }
      setLayers(prev => prev.map(l =>
        l.id === layerId ? { ...l, enabled: false, loading: false } : l
      ));
      return;
    }

    setLayers(prev => prev.map(l =>
      l.id === layerId ? { ...l, enabled: true, loading: true } : l
    ));

    try {
      if (layerId === "competitor_stores") {
        await loadCompetitorStoresLayer(map, L);
      } else if (layerId === "catchment_zones") {
        await loadCatchmentZonesLayer(map, L);
      } else if (layerId === "irve") {
        await loadIRVELayer(map, L);
      } else if (layerId === "poi_restaurant" || layerId === "poi_shop") {
        await loadPOILayer(map, L, layerId);
      } else if (["departements", "regions", "communes", "academies"].includes(layerId)) {
        await loadBoundaryLayer(map, L, layerId);
      }
    } catch (err) {
      console.error(`Failed to load layer ${layerId}:`, err);
      setLayers(prev => prev.map(l =>
        l.id === layerId ? { ...l, enabled: false, loading: false } : l
      ));
    } finally {
      setLayers(prev => prev.map(l =>
        l.id === layerId ? { ...l, loading: false } : l
      ));
    }
  };

  const loadIRVELayer = async (map: any, L: any) => {
    const center = map.getCenter();
    const res = await fetch(
      `${API_BASE}/layers/irve?lat=${center.lat}&lng=${center.lng}&radius_km=50&limit=500`
    );
    if (!res.ok) return;

    const data = await res.json();
    setIrveStations(data.stations);
    setIrveStats(null);

    fetch(`${API_BASE}/layers/irve/stats`).then(r => r.json()).then(setIrveStats).catch(() => {});

    const layerGroup = L.layerGroup();

    const greenIcon = new L.Icon({
      iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png",
      shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
      iconSize: [20, 33],
      iconAnchor: [10, 33],
      popupAnchor: [1, -28],
      shadowSize: [33, 33],
    });

    data.stations.forEach((station: IRVEStation) => {
      if (station.latitude && station.longitude) {
        L.marker([station.latitude, station.longitude], { icon: greenIcon })
          .bindPopup(`
            <b>${station.nom}</b><br>
            ${station.adresse}<br>
            <span class="text-sm">${station.nb_points_charge} points • ${station.puissance_max_kw}kW</span><br>
            <span class="text-xs text-gray-500">${station.operateur}</span>
          `)
          .addTo(layerGroup);
      }
    });

    layerGroup.addTo(map);
    layerGroupsRef.current.set("irve", layerGroup);
  };

  const loadPOILayer = async (map: any, L: any, layerId: string) => {
    try {
      const center = map.getCenter();
      const category = layerId === "poi_restaurant" ? "restaurant,cafe" : "shop,supermarket,bakery";

      const res = await fetch(
        `${API_BASE}/layers/poi?lat=${center.lat}&lng=${center.lng}&radius_m=3000&categories=${category}`
      );
      if (!res.ok) return;

      const data = await res.json();
      setPois(prev => [...prev, ...(data.pois || [])]);

      const layerGroup = L.layerGroup();
      const color = layerId === "poi_restaurant" ? "orange" : "violet";

      const icon = new L.Icon({
        iconUrl: `https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-${color}.png`,
        shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
        iconSize: [18, 30],
        iconAnchor: [9, 30],
        popupAnchor: [1, -25],
        shadowSize: [30, 30],
      });

      (data.pois || []).forEach((poi: POI) => {
        if (poi.latitude && poi.longitude) {
          L.marker([poi.latitude, poi.longitude], { icon })
            .bindPopup(`<b>${poi.name}</b><br><span class="text-xs">${poi.category}</span>`)
            .addTo(layerGroup);
        }
      });

      layerGroup.addTo(map);
      layerGroupsRef.current.set(layerId, layerGroup);
    } catch (err) {
      console.error(`Error loading POI ${layerId}:`, err);
    }
  };

  const loadBoundaryLayer = async (map: any, L: any, layerId: string) => {
    try {
      const res = await fetch(`${API_BASE}/layers/boundaries/${layerId}`);
      if (!res.ok) return;

      const geojson = await res.json();
      if (!geojson.features || geojson.features.length === 0) return;

      const colorMap: Record<string, string> = {
        regions: "#8b5cf6",
        departements: "#3b82f6",
        communes: "#6366f1",
        academies: "#14b8a6",
      };
      const weightMap: Record<string, number> = {
        regions: 3,
        departements: 2,
        communes: 1,
        academies: 2,
      };
      const color = colorMap[layerId] || "#3b82f6";
      const weight = weightMap[layerId] || 2;

      const geoJsonLayer = L.geoJSON(geojson, {
        style: {
          color,
          weight,
          fillColor: color,
          fillOpacity: 0.08,
        },
        onEachFeature: (feature: any, layer: any) => {
          const props = feature.properties || {};
          const name = props.nom || props.academie || props.name || "Sans nom";
          const code = props.code || props.codeDepartement || "";
          const tooltip = code ? `${name} (${code})` : name;
          layer.bindTooltip(tooltip, { sticky: true });
          layer.on("mouseover", () => {
            layer.setStyle({ fillOpacity: 0.25, weight: weight + 1 });
          });
          layer.on("mouseout", () => {
            layer.setStyle({ fillOpacity: 0.08, weight });
          });
        },
      });

      geoJsonLayer.addTo(map);
      layerGroupsRef.current.set(layerId, geoJsonLayer);
    } catch (err) {
      console.error(`Error loading ${layerId}:`, err);
    }
  };

  // Store all competitor data for viewport-based rendering
  const competitorStoreDataRef = useRef<CompetitorStoreGroup[]>([]);

  const gmbAutoEnrichedRef = useRef(false);

  const loadCompetitorStoresLayer = async (map: any, L: any) => {
    const res = await fetch(`${API_BASE}/geo/competitor-stores?include_stores=true`, { headers: authHeaders() });
    if (!res.ok) return;

    const data = await res.json();
    const groups: CompetitorStoreGroup[] = data.competitors || [];
    setCompetitorStoreGroups(groups);
    competitorStoreDataRef.current = groups;

    // Render visible stores
    renderCompetitorStoresInView(map, L, groups);

    // Re-render on move
    const onMoveEnd = () => {
      renderCompetitorStoresInView(map, L, competitorStoreDataRef.current);
    };
    map.on("moveend", onMoveEnd);

    // Store cleanup function
    (layerGroupsRef.current as any).__competitorMoveHandler = onMoveEnd;

    // Auto-enrich GMB once if no ratings exist yet
    const hasRatings = groups.some(g => g.avg_rating != null);
    if (!hasRatings && groups.length > 0 && !gmbAutoEnrichedRef.current) {
      gmbAutoEnrichedRef.current = true;
      // Fire and forget — don't block the layer display
      runGmbEnrichment(map, L);
    }
  };

  const runGmbEnrichment = async (map: any, L: any, force = false) => {
    setGmbEnriching(true);
    try {
      // Try real GMB enrichment first, fallback to demo if not configured
      let res = await fetch(`${API_BASE}/geo/stores/enrich-gmb?force=${force}&max_per_run=50`, {
        method: "POST",
        headers: authHeaders(),
      });
      if (res.status === 503) {
        // GMB APIs not configured, fallback to demo
        res = await fetch(`${API_BASE}/geo/stores/enrich-gmb-demo?force=${force}`, {
          method: "POST",
          headers: authHeaders(),
        });
      }
      if (!res.ok) throw new Error("Enrichissement échoué");
      // Reload to get updated ratings
      const res2 = await fetch(`${API_BASE}/geo/competitor-stores?include_stores=true`, { headers: authHeaders() });
      if (!res2.ok) return;
      const data = await res2.json();
      const groups: CompetitorStoreGroup[] = data.competitors || [];
      setCompetitorStoreGroups(groups);
      competitorStoreDataRef.current = groups;
      renderCompetitorStoresInView(map, L, groups);
    } catch (err) {
      console.error("GMB enrichment error:", err);
    } finally {
      setGmbEnriching(false);
    }
  };

  const handleEnrichGmb = async () => {
    const map = mapInstanceRef.current;
    const L = leafletRef.current;
    if (!map || !L) return;
    await runGmbEnrichment(map, L, true);
  };

  const getRatingColor = (rating: number | undefined, fallback: string): string => {
    if (rating == null) return fallback;
    if (rating >= 4.0) return "#22c55e"; // green
    if (rating >= 3.5) return "#eab308"; // yellow
    if (rating >= 3.0) return "#f97316"; // orange
    return "#ef4444"; // red
  };

  const renderCompetitorStoresInView = (map: any, L: any, groups: CompetitorStoreGroup[]) => {
    // Remove old layer
    const oldLayer = layerGroupsRef.current.get("competitor_stores");
    if (oldLayer) map.removeLayer(oldLayer);

    const zoom = map.getZoom();
    // Scale marker size based on zoom
    const size = zoom >= 12 ? 48 : zoom >= 10 ? 40 : zoom >= 8 ? 32 : 24;
    const borderWidth = zoom >= 10 ? 4 : 3;

    // Use MarkerClusterGroup for performance with thousands of points
    const clusterGroup = (L as any).markerClusterGroup({
      maxClusterRadius: zoom >= 10 ? 30 : zoom >= 8 ? 50 : 80,
      disableClusteringAtZoom: 13,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
      chunkedLoading: true,
      iconCreateFunction: (cluster: any) => {
        const count = cluster.getChildCount();
        const clusterSize = count > 100 ? 44 : count > 30 ? 36 : 28;
        const bg = count > 100 ? "#7c3aed" : count > 30 ? "#2563eb" : "#0891b2";
        return L.divIcon({
          className: "",
          html: `<div style="width:${clusterSize}px;height:${clusterSize}px;border-radius:50%;background:${bg};color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:${clusterSize > 36 ? 13 : 11}px;box-shadow:0 2px 6px rgba(0,0,0,0.3);border:2px solid rgba(255,255,255,0.8);">${count}</div>`,
          iconSize: [clusterSize, clusterSize],
          iconAnchor: [clusterSize / 2, clusterSize / 2],
        });
      },
    });

    groups.forEach((group) => {
      group.stores.forEach((store) => {
        if (!store.latitude || !store.longitude) return;

        // Stroke color based on GMB rating (green=good, red=bad), fallback to brand color
        const rating = store.google_rating;
        const strokeColor = rating != null
          ? rating >= 4.0 ? "#16a34a"   // green-600
            : rating >= 3.5 ? "#ca8a04" // yellow-600
            : rating >= 3.0 ? "#ea580c" // orange-600
            : "#dc2626"                  // red-600
          : group.color;

        let popupHtml =
          `<b>${store.name || store.brand_name}</b><br>` +
          `<span style="color:${group.color};font-weight:600">${group.competitor_name}</span><br>` +
          `${store.city}${store.postal_code ? ` (${store.postal_code})` : ""}`;

        if (store.google_rating != null) {
          popupHtml += `<br><span style="font-size:13px"><img src="/google-logo.svg" style="height:14px;width:14px;vertical-align:middle;display:inline-block;margin-right:3px"> <b>${store.google_rating}</b>/5</span>`;
          if (store.google_reviews_count != null) {
            popupHtml += ` <span style="color:#666;font-size:12px">(${store.google_reviews_count.toLocaleString()} avis)</span>`;
          }
        }

        if (group.logo_url) {
          const icon = L.divIcon({
            className: "",
            html: `<div style="width:${size}px;height:${size}px;border-radius:50%;border:${borderWidth}px solid ${strokeColor};background:#fff;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,0.25);display:flex;align-items:center;justify-content:center;"><img src="${group.logo_url}" style="width:${size - borderWidth * 2}px;height:${size - borderWidth * 2}px;border-radius:50%;object-fit:contain;" onerror="this.parentElement.innerHTML='<span style=\\'font-size:${Math.round(size * 0.4)}px;font-weight:700;color:${strokeColor}\\'>${group.competitor_name.charAt(0)}</span>'" /></div>`,
            iconSize: [size, size],
            iconAnchor: [size / 2, size / 2],
          });
          L.marker([store.latitude, store.longitude], { icon })
            .addTo(clusterGroup)
            .bindPopup(popupHtml);
        } else {
          const icon = L.divIcon({
            className: "",
            html: `<div style="width:${size}px;height:${size}px;border-radius:50%;border:${borderWidth}px solid ${strokeColor};background:#fff;display:flex;align-items:center;justify-content:center;box-shadow:0 1px 4px rgba(0,0,0,0.25);"><span style="font-size:${Math.round(size * 0.4)}px;font-weight:700;color:${strokeColor};line-height:1;">${group.competitor_name.charAt(0)}</span></div>`,
            iconSize: [size, size],
            iconAnchor: [size / 2, size / 2],
          });
          L.marker([store.latitude, store.longitude], { icon })
            .addTo(clusterGroup)
            .bindPopup(popupHtml);
        }
      });
    });

    clusterGroup.addTo(map);
    layerGroupsRef.current.set("competitor_stores", clusterGroup);
  };

  // =========================================================================
  // Catchment zones layer
  // =========================================================================

  const loadCatchmentZonesLayer = async (map: any, L: any) => {
    const radiusKm = catchmentRadiusRef.current;

    // Fetch stats
    const res = await fetch(`${API_BASE}/geo/catchment-zones?radius_km=${radiusKm}`, { headers: authHeaders() });
    if (!res.ok) return;

    const data = await res.json();
    setCatchmentData(data);

    // We need store coordinates — reuse competitorStoreDataRef if available, otherwise fetch
    let storeGroups = competitorStoreDataRef.current;
    if (!storeGroups || storeGroups.length === 0) {
      const storeRes = await fetch(`${API_BASE}/geo/competitor-stores?include_stores=true`, { headers: authHeaders() });
      if (storeRes.ok) {
        const storeData = await storeRes.json();
        storeGroups = storeData.competitors || [];
        competitorStoreDataRef.current = storeGroups;
      }
    }

    // Render circles
    renderCatchmentZonesInView(map, L, storeGroups, radiusKm);

    // Re-render on move
    const onMoveEnd = () => {
      renderCatchmentZonesInView(map, L, competitorStoreDataRef.current, catchmentRadiusRef.current);
    };
    map.on("moveend", onMoveEnd);
    (layerGroupsRef.current as any).__catchmentMoveHandler = onMoveEnd;
  };

  const renderCatchmentZonesInView = (map: any, L: any, groups: CompetitorStoreGroup[], radiusKm: number) => {
    const oldLayer = layerGroupsRef.current.get("catchment_zones");
    if (oldLayer) map.removeLayer(oldLayer);

    const zoom = map.getZoom();
    if (zoom < 6) return; // Too zoomed out

    const bounds = map.getBounds();
    // Pad bounds by radius
    const padDeg = radiusKm / 111;
    const paddedBounds = L.latLngBounds(
      [bounds.getSouth() - padDeg, bounds.getWest() - padDeg],
      [bounds.getNorth() + padDeg, bounds.getEast() + padDeg]
    );

    const layerGroup = L.layerGroup();

    groups.forEach((group) => {
      group.stores.forEach((store) => {
        if (!store.latitude || !store.longitude) return;
        if (!paddedBounds.contains([store.latitude, store.longitude])) return;

        L.circle([store.latitude, store.longitude], {
          radius: radiusKm * 1000,
          fillColor: group.color,
          color: group.color,
          fillOpacity: 0.08,
          weight: 1,
          interactive: false,
        }).addTo(layerGroup);
      });
    });

    layerGroup.addTo(map);
    layerGroupsRef.current.set("catchment_zones", layerGroup);
  };

  const loadLayersForArea = (lat: number, lng: number, radiusKm: number) => {
    layers.forEach(layer => {
      if (layer.enabled) {
        const map = mapInstanceRef.current;
        const L = leafletRef.current;
        if (!map || !L) return;

        const existingLayer = layerGroupsRef.current.get(layer.id);
        if (existingLayer) {
          map.removeLayer(existingLayer);
        }

        if (layer.id === "irve") {
          loadIRVELayer(map, L);
        } else if (layer.id.startsWith("poi_")) {
          loadPOILayer(map, L, layer.id);
        }
      }
    });
  };

  // =========================================================================
  // Utilities
  // =========================================================================

  const formatNumber = (n: number) => {
    if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
    if (n >= 1000) return `${(n / 1000).toFixed(0)}k`;
    return n.toLocaleString("fr-FR");
  };

  const enabledLayersCount = layers.filter(l => l.enabled).length;

  // =========================================================================
  // Render
  // =========================================================================

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Carte principale */}
        <div className="lg:col-span-2 space-y-3">
          {/* Controls bar */}
          <div className="bg-white rounded-xl border shadow-sm p-4">
            <div className="flex flex-wrap items-center gap-4">
              {/* Mode selection */}
              <div className="flex items-center gap-2 bg-gray-50 rounded-lg p-1">
                {[
                  { value: "radius", label: "Rayon", icon: Target },
                  { value: "postal_code", label: "Code postal", icon: Navigation },
                  { value: "iris", label: "IRIS", icon: Layers },
                ].map((mode) => (
                  <button
                    key={mode.value}
                    onClick={() => setAnalysisMode(mode.value as AnalysisMode)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                      analysisMode === mode.value
                        ? "bg-white text-indigo-600 shadow-sm"
                        : "text-gray-600 hover:text-gray-900"
                    }`}
                  >
                    <mode.icon className="h-3.5 w-3.5" />
                    {mode.label}
                  </button>
                ))}
              </div>

              <div className="h-6 w-px bg-gray-200 hidden sm:block" />

              {/* Radius slider */}
              {analysisMode === "radius" && (
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min="1"
                    max="50"
                    value={radius}
                    onChange={(e) => setRadius(parseInt(e.target.value))}
                    className="w-28 accent-indigo-600"
                  />
                  <span className="text-sm font-semibold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">
                    {radius} km
                  </span>
                </div>
              )}

              {/* Postal code input */}
              {analysisMode === "postal_code" && (
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <input
                      type="text"
                      placeholder="75001"
                      value={postalCode}
                      onChange={(e) => setPostalCode(e.target.value.replace(/\D/g, "").slice(0, 5))}
                      className="text-sm border rounded-lg px-3 py-1.5 w-24 bg-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                  <button
                    onClick={analyzeByPostalCode}
                    disabled={searchLoading || postalCode.length !== 5}
                    className="flex items-center gap-1.5 text-sm bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-1.5 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
                  >
                    <Search className="h-3.5 w-3.5" />
                    {searchLoading ? "..." : "Analyser"}
                  </button>
                </div>
              )}

              {/* IRIS toggle */}
              {analysisMode === "iris" && (
                <button
                  onClick={() => setShowIrisLayer(!showIrisLayer)}
                  className={`flex items-center gap-2 text-sm px-4 py-1.5 rounded-lg font-medium transition-all ${
                    showIrisLayer
                      ? "bg-indigo-100 text-indigo-700 ring-2 ring-indigo-200"
                      : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                  }`}
                >
                  <Layers className="h-4 w-4" />
                  {showIrisLayer ? "IRIS actif" : "Activer IRIS"}
                  {irisLoading && <RefreshCw className="h-3 w-3 animate-spin ml-1" />}
                </button>
              )}

              <div className="flex-1" />

              {/* Layers toggle */}
              <button
                onClick={() => setLayersPanelOpen(!layersPanelOpen)}
                className={`flex items-center gap-2 text-sm px-4 py-1.5 rounded-lg font-medium transition-all ${
                  layersPanelOpen || enabledLayersCount > 0
                    ? "bg-purple-100 text-purple-700"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                <Layers className="h-4 w-4" />
                <span>Couches</span>
                {enabledLayersCount > 0 && (
                  <span className="bg-purple-600 text-white text-xs px-1.5 py-0.5 rounded-full min-w-[18px] text-center">
                    {enabledLayersCount}
                  </span>
                )}
                {layersPanelOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              </button>
            </div>

            {/* Layers panel */}
            {layersPanelOpen && (
              <div className="mt-4 pt-4 border-t">
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7 gap-2">
                  {layers.map(layer => (
                    <button
                      key={layer.id}
                      onClick={() => toggleLayer(layer.id)}
                      className={`relative flex flex-col items-center gap-1 p-3 rounded-xl border-2 transition-all ${
                        layer.enabled
                          ? "border-current bg-gradient-to-b from-white to-gray-50 shadow-sm"
                          : "border-transparent bg-gray-50 hover:bg-gray-100"
                      }`}
                      style={{ color: layer.enabled ? layer.color : undefined }}
                    >
                      {layer.loading ? (
                        <RefreshCw className="h-5 w-5 animate-spin" />
                      ) : (
                        <div className={`p-2 rounded-lg ${layer.enabled ? "bg-current/10" : "bg-gray-200"}`}>
                          {layer.icon}
                        </div>
                      )}
                      <span className={`text-xs font-medium ${layer.enabled ? "" : "text-gray-600"}`}>
                        {layer.name}
                      </span>
                      <span className="text-[10px] text-gray-400">{layer.description}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Map */}
          <div className="bg-white rounded-xl border shadow-sm overflow-hidden relative">
            <div
              ref={mapRef}
              className="h-[500px] bg-gray-100"
              style={{ zIndex: 0 }}
            />

            {/* Map overlay hint */}
            {!zoneAnalysis && analysisMode === "radius" && mapReady && (
              <div className="absolute bottom-4 left-1/2 -translate-x-1/2 pointer-events-none" style={{ zIndex: 1000 }}>
                <div className="flex items-center gap-2 bg-black/75 backdrop-blur-sm text-white text-sm px-4 py-2 rounded-full shadow-lg animate-pulse">
                  <MousePointer className="h-4 w-4" />
                  Cliquez sur la carte pour analyser une zone
                </div>
              </div>
            )}
          </div>

          {/* IRVE Stats bar */}
          {layers.find(l => l.id === "irve")?.enabled && irveStats && (
            <div className="bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl border border-green-200 p-4">
              <div className="flex items-center gap-2 mb-3">
                <div className="p-1.5 bg-green-500 rounded-lg">
                  <Zap className="h-4 w-4 text-white" />
                </div>
                <span className="text-sm font-semibold text-green-800">Bornes de recharge IRVE</span>
                <span className="text-xs text-green-600 bg-green-100 px-2 py-0.5 rounded-full ml-auto">
                  France entière
                </span>
              </div>
              <div className="grid grid-cols-4 gap-4">
                {[
                  { label: "Stations", value: irveStats.total_stations?.toLocaleString() || "0" },
                  { label: "Points de charge", value: irveStats.total_points_charge?.toLocaleString() || "0" },
                  { label: "Puissance moy.", value: `${irveStats.puissance_moyenne_kw || 0} kW` },
                  { label: "Accessibles PMR", value: `${irveStats.pct_accessibles_pmr || 0}%` },
                ].map((stat, i) => (
                  <div key={i} className="text-center">
                    <div className="text-xl font-bold text-green-700">{stat.value}</div>
                    <div className="text-xs text-green-600">{stat.label}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Competitor Stores Stats bar */}
          {layers.find(l => l.id === "competitor_stores")?.enabled && competitorStoreGroups.length > 0 && (
            <div className="bg-gradient-to-r from-red-50 to-orange-50 rounded-xl border border-red-200 p-4">
              <div className="flex items-center gap-2 mb-3">
                <div className="p-1.5 bg-red-500 rounded-lg">
                  <Store className="h-4 w-4 text-white" />
                </div>
                <span className="text-sm font-semibold text-red-800">Magasins concurrents</span>
                <span className="text-xs text-red-600 bg-red-100 px-2 py-0.5 rounded-full ml-auto">
                  {competitorStoreGroups.reduce((sum, g) => sum + g.total, 0).toLocaleString()} points
                </span>
              </div>

              {/* GMB Ratings by competitor - sorted by avg_rating */}
              <div className="space-y-1.5 mb-3">
                {competitorStoreGroups.some(g => g.avg_rating != null) ? (
                  [...competitorStoreGroups]
                    .filter(g => g.avg_rating != null)
                    .sort((a, b) => (b.avg_rating || 0) - (a.avg_rating || 0))
                    .map((group, idx, arr) => {
                      const rating = group.avg_rating || 0;
                      const rowStyle = rating >= 4.0
                        ? "bg-green-50 border-green-200"
                        : rating >= 3.5
                          ? "bg-yellow-50 border-yellow-200"
                          : rating >= 3.0
                            ? "bg-orange-50 border-orange-200"
                            : "bg-red-50 border-red-200";
                      return (
                      <div
                        key={group.competitor_id}
                        className={`flex items-center gap-2 rounded-lg px-2.5 py-1.5 border ${rowStyle}`}
                      >
                        {group.logo_url ? (
                          <img src={group.logo_url} alt="" className="w-5 h-5 rounded-full flex-shrink-0 object-contain border-2" style={{ borderColor: group.color }} />
                        ) : (
                          <div className="w-5 h-5 rounded-full flex-shrink-0 border-2 flex items-center justify-center bg-white" style={{ borderColor: group.color }}>
                            <span className="text-[8px] font-bold" style={{ color: group.color }}>{group.competitor_name.charAt(0)}</span>
                          </div>
                        )}
                        <span className="text-xs font-medium text-gray-700 flex-1">{group.competitor_name}</span>
                        <span className="text-xs font-semibold" style={{ color: (group.avg_rating || 0) >= 4.0 ? "#16a34a" : (group.avg_rating || 0) >= 3.5 ? "#ca8a04" : "#dc2626" }}>
                          ⭐ {group.avg_rating}
                        </span>
                        <span className="text-[10px] text-gray-400">
                          {(group.total_reviews || 0) >= 1000 ? `${((group.total_reviews || 0) / 1000).toFixed(1)}K` : group.total_reviews} avis
                        </span>
                      </div>
                      );
                    })
                ) : (
                  // Skeleton / loading state while auto-enrichment runs
                  competitorStoreGroups.map((group) => (
                    <div key={group.competitor_id} className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 border bg-white/80 animate-pulse">
                      {group.logo_url ? (
                        <img src={group.logo_url} alt="" className="w-5 h-5 rounded-full flex-shrink-0 object-contain border-2" style={{ borderColor: group.color }} />
                      ) : (
                        <div className="w-5 h-5 rounded-full flex-shrink-0 border-2 flex items-center justify-center bg-white" style={{ borderColor: group.color }}>
                          <span className="text-[8px] font-bold" style={{ color: group.color }}>{group.competitor_name.charAt(0)}</span>
                        </div>
                      )}
                      <span className="text-xs font-medium text-gray-700 flex-1">{group.competitor_name}</span>
                      <span className="text-xs text-gray-300">⭐ —</span>
                      <span className="w-10 h-3 bg-gray-200 rounded" />
                    </div>
                  ))
                )}
              </div>

              {/* Refresh GMB button — always visible */}
              <button
                onClick={handleEnrichGmb}
                disabled={gmbEnriching}
                className="w-full flex items-center justify-center gap-2 px-3 py-1.5 bg-white/80 hover:bg-white border border-red-200 text-red-700 text-xs font-medium rounded-lg transition-all disabled:opacity-50"
              >
                <RefreshCw className={`h-3 w-3 ${gmbEnriching ? "animate-spin" : ""}`} />
                {gmbEnriching ? "Analyse GMB en cours..." : "Rafraîchir les notes Google"}
              </button>

              {/* Legend */}
              <div className="flex items-center gap-2 text-[10px] text-gray-500 pt-2 border-t border-red-100 mt-2">
                <span>Bordure = couleur enseigne</span>
              </div>
            </div>
          )}

          {/* Catchment Zones Stats panel */}
          {layers.find(l => l.id === "catchment_zones")?.enabled && catchmentData && (
            <div className="bg-gradient-to-r from-purple-50 to-violet-50 rounded-xl border border-purple-200 p-4">
              <div className="flex items-center gap-2 mb-3">
                <div className="p-1.5 bg-purple-500 rounded-lg">
                  <Target className="h-4 w-4 text-white" />
                </div>
                <span className="text-sm font-semibold text-purple-800">Zones de chalandise</span>
                <div className="flex gap-1 ml-auto">
                  {[5, 10, 15].map((r) => (
                    <button
                      key={r}
                      onClick={async () => {
                        setCatchmentRadius(r);
                        catchmentRadiusRef.current = r;
                        const map = mapInstanceRef.current;
                        const L = leafletRef.current;
                        if (!map || !L) return;
                        setLayers(prev => prev.map(l =>
                          l.id === "catchment_zones" ? { ...l, loading: true } : l
                        ));
                        await loadCatchmentZonesLayer(map, L);
                        setLayers(prev => prev.map(l =>
                          l.id === "catchment_zones" ? { ...l, loading: false } : l
                        ));
                      }}
                      className={`px-2 py-0.5 rounded text-xs font-medium transition-all ${
                        catchmentRadius === r
                          ? "bg-purple-600 text-white"
                          : "bg-white text-purple-600 border border-purple-200 hover:bg-purple-100"
                      }`}
                    >
                      {r} km
                    </button>
                  ))}
                </div>
              </div>

              {/* Per-competitor coverage */}
              <div className="space-y-2 mb-3">
                {catchmentData.competitors?.map((comp: any) => (
                  <div key={comp.competitor_id} className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: comp.color }} />
                    <span className="text-xs font-medium text-gray-700 w-24 truncate">{comp.competitor_name}</span>
                    <div className="flex-1 h-4 bg-white/80 rounded-full overflow-hidden border">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{ width: `${Math.max(comp.pct_population, 1)}%`, backgroundColor: comp.color, opacity: 0.7 }}
                      />
                    </div>
                    <span className="text-xs font-bold text-gray-700 w-12 text-right">{comp.pct_population}%</span>
                    <span className="text-[10px] text-gray-400 w-20 text-right">{formatNumber(comp.population_covered)} hab.</span>
                  </div>
                ))}
              </div>

              {/* Overlaps */}
              {catchmentData.overlaps?.length > 0 && (
                <div className="border-t border-purple-200 pt-2">
                  <div className="text-[10px] uppercase tracking-wider text-purple-500 font-medium mb-1.5">Chevauchements</div>
                  <div className="space-y-1">
                    {catchmentData.overlaps.slice(0, 3).map((o: any, i: number) => (
                      <div key={i} className="flex items-center gap-2 text-xs text-gray-600">
                        <span className="truncate">{o.competitor_a_name} / {o.competitor_b_name}</span>
                        <span className="ml-auto font-medium text-purple-700 whitespace-nowrap">{formatNumber(o.shared_population)} hab.</span>
                        <span className="text-[10px] text-gray-400 whitespace-nowrap">{o.shared_communes} communes</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="text-[10px] text-purple-400 mt-2 text-right">
                Calcul: {catchmentData.computation_time_ms}ms
              </div>
            </div>
          )}
        </div>

        {/* Panel d'analyse */}
        <div className="space-y-4">
          {loading ? (
            <Card className="overflow-hidden">
              <div className="bg-gradient-to-br from-indigo-500 to-purple-600 p-6 text-white">
                <div className="flex items-center gap-3">
                  <div className="animate-spin h-8 w-8 border-3 border-white border-t-transparent rounded-full" />
                  <div>
                    <div className="font-semibold">Analyse en cours</div>
                    <div className="text-sm opacity-80">Collecte des données INSEE...</div>
                  </div>
                </div>
              </div>
              <div className="p-6 space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="animate-pulse">
                    <div className="h-4 bg-gray-200 rounded w-3/4 mb-2" />
                    <div className="h-8 bg-gray-100 rounded w-1/2" />
                  </div>
                ))}
              </div>
            </Card>
          ) : !zoneAnalysis ? (
            /* Empty state - Engaging onboarding */
            <Card className="overflow-hidden">
              <div className="bg-gradient-to-br from-violet-50 to-indigo-50 border-b border-violet-100 p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-100 to-indigo-100 border border-violet-200/50">
                    <Sparkles className="h-5 w-5 text-violet-600" />
                  </div>
                  <div>
                    <div className="font-semibold text-lg text-foreground">Bienvenue</div>
                    <div className="text-sm text-muted-foreground">Commencez votre analyse</div>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  Explorez les données socio-démographiques, la mobilité et les loyers
                  pour toute zone en France.
                </p>
              </div>

              <div className="p-5 space-y-5">
                {/* Quick start */}
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-3">
                    <Target className="h-4 w-4 text-indigo-500" />
                    Comment démarrer
                  </div>
                  <div className="space-y-2">
                    {[
                      { icon: MousePointer, text: "Cliquez sur la carte", mode: "radius" },
                      { icon: Navigation, text: "Entrez un code postal", mode: "postal_code" },
                      { icon: Layers, text: "Sélectionnez une zone IRIS", mode: "iris" },
                    ].map((item, i) => (
                      <button
                        key={i}
                        onClick={() => setAnalysisMode(item.mode as AnalysisMode)}
                        className={`w-full flex items-center gap-3 p-3 rounded-lg text-left transition-all ${
                          analysisMode === item.mode
                            ? "bg-indigo-50 border-2 border-indigo-200"
                            : "bg-gray-50 border-2 border-transparent hover:bg-gray-100"
                        }`}
                      >
                        <div className={`p-2 rounded-lg ${
                          analysisMode === item.mode ? "bg-indigo-100" : "bg-white"
                        }`}>
                          <item.icon className={`h-4 w-4 ${
                            analysisMode === item.mode ? "text-indigo-600" : "text-gray-500"
                          }`} />
                        </div>
                        <span className={`text-sm font-medium ${
                          analysisMode === item.mode ? "text-indigo-700" : "text-gray-700"
                        }`}>
                          {item.text}
                        </span>
                        {analysisMode === item.mode && (
                          <ArrowRight className="h-4 w-4 text-indigo-500 ml-auto" />
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Quick locations */}
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-3">
                    <MapPin className="h-4 w-4 text-purple-500" />
                    Villes populaires
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {QUICK_LOCATIONS.map((loc) => (
                      <button
                        key={loc.name}
                        onClick={() => analyzeQuickLocation(loc)}
                        className="flex items-center gap-2 p-2.5 bg-gray-50 hover:bg-purple-50 rounded-lg transition-all group text-left"
                      >
                        <span className="text-lg">{loc.emoji}</span>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-800 group-hover:text-purple-700 truncate">
                            {loc.name}
                          </div>
                          <div className="text-xs text-gray-500">{loc.description}</div>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Features hint */}
                <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-lg p-4 border border-amber-100">
                  <div className="flex items-start gap-3">
                    <div className="p-1.5 bg-amber-100 rounded-lg shrink-0">
                      <PieChart className="h-4 w-4 text-amber-600" />
                    </div>
                    <div className="text-sm">
                      <div className="font-medium text-amber-800">Données incluses</div>
                      <div className="text-amber-700 mt-1 leading-relaxed">
                        Population, tranches d'âge, CSP, revenus, chômage, loyers, modes de transport...
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          ) : (
            /* Analysis results */
            <Card className="overflow-hidden">
              {/* Header with zone info */}
              <div className="bg-gradient-to-br from-indigo-500 to-purple-600 p-5 text-white">
                {(zoneAnalysis as any).iris_code ? (
                  <>
                    <div className="text-xs uppercase tracking-wider opacity-80 mb-1">Zone IRIS</div>
                    <div className="font-bold text-xl">{(zoneAnalysis as any).iris_name}</div>
                    <div className="text-sm opacity-90 mt-1">{(zoneAnalysis as any).commune_name}</div>
                  </>
                ) : (zoneAnalysis as any).commune_name ? (
                  <>
                    <div className="text-xs uppercase tracking-wider opacity-80 mb-1">Commune</div>
                    <div className="font-bold text-xl">{(zoneAnalysis as any).commune_name}</div>
                    <div className="text-sm opacity-90 mt-1">Code postal: {(zoneAnalysis as any).postal_code}</div>
                  </>
                ) : (
                  <>
                    <div className="text-xs uppercase tracking-wider opacity-80 mb-1">Zone analysée</div>
                    <div className="font-bold text-xl">Rayon de {zoneAnalysis.radius_km} km</div>
                    <div className="text-sm opacity-90 mt-1">
                      {zoneAnalysis.analysis.nb_communes} communes couvertes
                    </div>
                  </>
                )}
              </div>

              {/* Tabs */}
              <div className="flex border-b">
                {[
                  { id: "overview", label: "Aperçu" },
                  { id: "demo", label: "Démographie" },
                  { id: "communes", label: "Communes" },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`flex-1 px-4 py-3 text-sm font-medium transition-all ${
                      activeTab === tab.id
                        ? "text-indigo-600 border-b-2 border-indigo-600 bg-indigo-50/50"
                        : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              <div className="p-4 space-y-4 max-h-[500px] overflow-y-auto">
                {activeTab === "overview" && (
                  <>
                    {/* Key stats */}
                    <div className="grid grid-cols-2 gap-3">
                      <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-4 border border-blue-100">
                        <div className="flex items-center gap-2 text-blue-600 mb-2">
                          <Users className="h-4 w-4" />
                          <span className="text-xs font-medium uppercase tracking-wide">Population</span>
                        </div>
                        <div className="text-2xl font-bold text-blue-700">
                          {formatNumber(zoneAnalysis.analysis.population_totale)}
                        </div>
                      </div>

                      <div className="bg-gradient-to-br from-purple-50 to-pink-50 rounded-xl p-4 border border-purple-100">
                        <div className="flex items-center gap-2 text-purple-600 mb-2">
                          <Home className="h-4 w-4" />
                          <span className="text-xs font-medium uppercase tracking-wide">Loyer m²</span>
                        </div>
                        <div className="text-2xl font-bold text-purple-700">
                          {zoneAnalysis.analysis.loyer_moyen_m2_appartement
                            ? `${zoneAnalysis.analysis.loyer_moyen_m2_appartement.toFixed(0)}€`
                            : "N/A"}
                        </div>
                      </div>

                      <div className="bg-gradient-to-br from-emerald-50 to-teal-50 rounded-xl p-4 border border-emerald-100">
                        <div className="flex items-center gap-2 text-emerald-600 mb-2">
                          <TrendingUp className="h-4 w-4" />
                          <span className="text-xs font-medium uppercase tracking-wide">Densité</span>
                        </div>
                        <div className="text-2xl font-bold text-emerald-700">
                          {zoneAnalysis.analysis.densite_moyenne
                            ? formatNumber(Math.round(zoneAnalysis.analysis.densite_moyenne))
                            : "N/A"}
                          <span className="text-sm font-normal opacity-70">/km²</span>
                        </div>
                      </div>

                      <div className="bg-gradient-to-br from-orange-50 to-amber-50 rounded-xl p-4 border border-orange-100">
                        <div className="flex items-center gap-2 text-orange-600 mb-2">
                          <MapPin className="h-4 w-4" />
                          <span className="text-xs font-medium uppercase tracking-wide">Communes</span>
                        </div>
                        <div className="text-2xl font-bold text-orange-700">
                          {zoneAnalysis.analysis.nb_communes}
                        </div>
                      </div>
                    </div>

                    {/* Mobility */}
                    {zoneAnalysis.analysis.mobilite && (
                      <div className="bg-gray-50 rounded-xl p-4">
                        <div className="flex items-center gap-2 mb-3">
                          <Car className="h-4 w-4 text-gray-600" />
                          <span className="text-sm font-semibold text-gray-700">Mobilité domicile-travail</span>
                        </div>
                        <div className="grid grid-cols-4 gap-2">
                          {[
                            { icon: Car, label: "Voiture", value: zoneAnalysis.analysis.mobilite.pct_voiture, color: "text-blue-600" },
                            { icon: Train, label: "Transport", value: zoneAnalysis.analysis.mobilite.pct_transport_commun, color: "text-green-600" },
                            { icon: Bike, label: "Vélo", value: zoneAnalysis.analysis.mobilite.pct_velo_2roues, color: "text-amber-600" },
                            { icon: Users, label: "Marche", value: zoneAnalysis.analysis.mobilite.pct_marche, color: "text-purple-600" },
                          ].map((mode) => (
                            <div key={mode.label} className="text-center bg-white rounded-lg p-2 shadow-sm">
                              <mode.icon className={`h-4 w-4 mx-auto mb-1 ${mode.color}`} />
                              <div className={`text-lg font-bold ${mode.color}`}>{mode.value}%</div>
                              <div className="text-[10px] text-gray-500">{mode.label}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Quick socio-demo */}
                    {zoneAnalysis.analysis.socio_demo && (
                      <div className="grid grid-cols-2 gap-2">
                        {zoneAnalysis.analysis.socio_demo.revenu_median && (
                          <div className="bg-white rounded-lg p-3 border flex items-center gap-3">
                            <div className="p-2 bg-amber-50 rounded-lg">
                              <Euro className="h-4 w-4 text-amber-600" />
                            </div>
                            <div>
                              <div className="text-xs text-gray-500">Revenu médian</div>
                              <div className="font-bold text-gray-800">
                                {formatNumber(Math.round(zoneAnalysis.analysis.socio_demo.revenu_median))}€
                              </div>
                            </div>
                          </div>
                        )}
                        {zoneAnalysis.analysis.socio_demo.taux_chomage !== null && (
                          <div className="bg-white rounded-lg p-3 border flex items-center gap-3">
                            <div className="p-2 bg-rose-50 rounded-lg">
                              <Briefcase className="h-4 w-4 text-rose-600" />
                            </div>
                            <div>
                              <div className="text-xs text-gray-500">Chômage</div>
                              <div className="font-bold text-gray-800">
                                {zoneAnalysis.analysis.socio_demo.taux_chomage.toFixed(1)}%
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </>
                )}

                {activeTab === "demo" && zoneAnalysis.analysis.socio_demo && (
                  <>
                    {/* Genre distribution */}
                    {zoneAnalysis.analysis.socio_demo.genre && (
                      <div className="bg-white rounded-xl p-4 border">
                        <div className="text-sm font-semibold text-gray-700 mb-3">Répartition homme / femme</div>
                        <div className="flex items-center gap-3">
                          <div className="flex-1">
                            <div className="flex rounded-full overflow-hidden h-5">
                              <div
                                className="bg-gradient-to-r from-blue-400 to-blue-500 flex items-center justify-center"
                                style={{ width: `${zoneAnalysis.analysis.socio_demo.genre.pct_hommes}%` }}
                              >
                                <span className="text-[10px] font-bold text-white">{zoneAnalysis.analysis.socio_demo.genre.pct_hommes}%</span>
                              </div>
                              <div
                                className="bg-gradient-to-r from-pink-400 to-pink-500 flex items-center justify-center"
                                style={{ width: `${zoneAnalysis.analysis.socio_demo.genre.pct_femmes}%` }}
                              >
                                <span className="text-[10px] font-bold text-white">{zoneAnalysis.analysis.socio_demo.genre.pct_femmes}%</span>
                              </div>
                            </div>
                            <div className="flex justify-between mt-2">
                              <div className="flex items-center gap-1.5">
                                <div className="h-2.5 w-2.5 rounded-full bg-blue-500" />
                                <span className="text-xs text-gray-600">Hommes</span>
                                <span className="text-xs font-bold text-gray-700">{formatNumber(zoneAnalysis.analysis.socio_demo.genre.hommes)}</span>
                              </div>
                              <div className="flex items-center gap-1.5">
                                <div className="h-2.5 w-2.5 rounded-full bg-pink-500" />
                                <span className="text-xs text-gray-600">Femmes</span>
                                <span className="text-xs font-bold text-gray-700">{formatNumber(zoneAnalysis.analysis.socio_demo.genre.femmes)}</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Key indicators */}
                    <div className="grid grid-cols-2 gap-3">
                      {zoneAnalysis.analysis.socio_demo.taux_mobinautes !== null && (
                        <div className="bg-gradient-to-br from-violet-50 to-indigo-50 rounded-xl p-4 border border-violet-100">
                          <div className="flex items-center gap-2 text-violet-600 mb-2">
                            <Smartphone className="h-4 w-4" />
                            <span className="text-xs font-medium">Mobinautes</span>
                          </div>
                          <div className="text-2xl font-bold text-violet-700">
                            {zoneAnalysis.analysis.socio_demo.taux_mobinautes.toFixed(1)}%
                          </div>
                          <div className="text-[10px] text-violet-500 mt-0.5">Taux de pénétration mobile</div>
                        </div>
                      )}
                      {zoneAnalysis.analysis.socio_demo.taux_chomage !== null && (
                        <div className="bg-gradient-to-br from-rose-50 to-pink-50 rounded-xl p-4 border border-rose-100">
                          <div className="flex items-center gap-2 text-rose-600 mb-2">
                            <Briefcase className="h-4 w-4" />
                            <span className="text-xs font-medium">Chômage</span>
                          </div>
                          <div className="text-2xl font-bold text-rose-700">
                            {zoneAnalysis.analysis.socio_demo.taux_chomage.toFixed(1)}%
                          </div>
                        </div>
                      )}
                      {zoneAnalysis.analysis.socio_demo.pct_proprietaires !== null && (
                        <div className="bg-gradient-to-br from-cyan-50 to-blue-50 rounded-xl p-4 border border-cyan-100">
                          <div className="flex items-center gap-2 text-cyan-600 mb-2">
                            <UserCheck className="h-4 w-4" />
                            <span className="text-xs font-medium">Propriétaires</span>
                          </div>
                          <div className="text-2xl font-bold text-cyan-700">
                            {zoneAnalysis.analysis.socio_demo.pct_proprietaires.toFixed(1)}%
                          </div>
                        </div>
                      )}
                      {zoneAnalysis.analysis.socio_demo.revenu_median !== null && (
                        <div className="bg-gradient-to-br from-amber-50 to-yellow-50 rounded-xl p-4 border border-amber-100">
                          <div className="flex items-center gap-2 text-amber-600 mb-2">
                            <Euro className="h-4 w-4" />
                            <span className="text-xs font-medium">Revenu médian</span>
                          </div>
                          <div className="text-2xl font-bold text-amber-700">
                            {formatNumber(Math.round(zoneAnalysis.analysis.socio_demo.revenu_median))}€
                          </div>
                        </div>
                      )}
                      {zoneAnalysis.analysis.socio_demo.taux_pauvrete !== null && (
                        <div className="bg-gradient-to-br from-gray-50 to-slate-50 rounded-xl p-4 border border-gray-200">
                          <div className="flex items-center gap-2 text-gray-600 mb-2">
                            <PieChart className="h-4 w-4" />
                            <span className="text-xs font-medium">Pauvreté</span>
                          </div>
                          <div className="text-2xl font-bold text-gray-700">
                            {zoneAnalysis.analysis.socio_demo.taux_pauvrete.toFixed(1)}%
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Age distribution */}
                    {zoneAnalysis.analysis.socio_demo.tranches_age && (
                      <div className="bg-white rounded-xl p-4 border">
                        <div className="text-sm font-semibold text-gray-700 mb-3">Tranches d'âge</div>
                        <div className="space-y-2">
                          {Object.entries(zoneAnalysis.analysis.socio_demo.tranches_age).map(([age, pct]) => (
                            <div key={age} className="flex items-center gap-3">
                              <span className="w-12 text-xs text-gray-600 font-medium">{age}</span>
                              <div className="flex-1 bg-gray-100 rounded-full h-3 overflow-hidden">
                                <div
                                  className="bg-gradient-to-r from-indigo-500 to-purple-500 h-3 rounded-full transition-all"
                                  style={{ width: `${Math.min((pct as number) * 3, 100)}%` }}
                                />
                              </div>
                              <span className="w-12 text-xs font-bold text-gray-700 text-right">
                                {(pct as number).toFixed(1)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* CSP */}
                    {zoneAnalysis.analysis.socio_demo.csp && (
                      <div className="bg-white rounded-xl p-4 border">
                        <div className="text-sm font-semibold text-gray-700 mb-3">Catégories socio-professionnelles</div>
                        <div className="space-y-2">
                          {Object.entries(zoneAnalysis.analysis.socio_demo.csp)
                            .sort((a, b) => (b[1] as number) - (a[1] as number))
                            .map(([csp, pct]) => (
                              <div key={csp} className="flex items-center gap-3">
                                <span className="w-28 text-xs text-gray-600 font-medium capitalize truncate" title={csp}>
                                  {csp.replace(/_/g, " ")}
                                </span>
                                <div className="flex-1 bg-gray-100 rounded-full h-3 overflow-hidden">
                                  <div
                                    className="bg-gradient-to-r from-emerald-400 to-teal-500 h-3 rounded-full"
                                    style={{ width: `${Math.min((pct as number) * 2, 100)}%` }}
                                  />
                                </div>
                                <span className="w-12 text-xs font-bold text-gray-700 text-right">
                                  {(pct as number).toFixed(1)}%
                                </span>
                              </div>
                            ))}
                        </div>
                      </div>
                    )}
                  </>
                )}

                {activeTab === "communes" && (
                  <div className="space-y-2">
                    {zoneAnalysis.communes.slice(0, 15).map((commune, i) => (
                      <div
                        key={commune.code}
                        className="flex items-center gap-3 p-3 bg-white rounded-lg border hover:border-indigo-200 transition-colors"
                      >
                        <span className="w-6 h-6 flex items-center justify-center text-xs font-bold text-white bg-gradient-to-br from-indigo-500 to-purple-600 rounded-full">
                          {i + 1}
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-800 truncate">
                            {commune.nom_commune}
                          </div>
                          <div className="text-xs text-gray-500">
                            {commune.distance_km.toFixed(1)} km
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm font-bold text-blue-600">
                            {formatNumber(commune.population)}
                          </div>
                          <div className="text-xs text-purple-600">
                            {commune.loyer_m2_appartement
                              ? `${commune.loyer_m2_appartement.toFixed(0)}€/m²`
                              : "-"}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="border-t p-3 bg-gray-50">
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span>Source: INSEE, data.gouv.fr</span>
                  <button
                    onClick={() => setZoneAnalysis(null)}
                    className="text-indigo-600 hover:text-indigo-800 font-medium"
                  >
                    Nouvelle analyse
                  </button>
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
