import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Loader2,
  MapPin,
  Plus,
  Trash2,
  RefreshCcw,
  AlertCircle,
  AlertTriangle,
  ExternalLink,
  Navigation,
  ArrowUp,
  ArrowDown,
  Search,
  RotateCcw,
  Compass,
  CheckCircle2,
  Maximize2,
} from "lucide-react";
import { optimizeRoute } from "@/lib/api";

export interface Point {
  name: string;
  lat?: number | null;
  lon?: number | null;
  category?: string;
  rating?: number;
}

interface RouteOptimizerBoxProps {
  points?: Point[];
  destinationName?: string;
  destination?: any;
  attractions?: any[];
  onRouteStopsChange?: (stops: Point[]) => void;
}

export const RouteOptimizerBox = ({
  points: initialPoints = [],
  destinationName,
  destination,
  attractions: propAttractions = [],
  onRouteStopsChange,
}: RouteOptimizerBoxProps) => {
  const destName =
    destinationName ||
    (typeof destination === "string" ? destination : destination?.name) ||
    "Destination";

  const allAvailableAttractions = useMemo(() => {
    if (propAttractions && propAttractions.length > 0) return propAttractions;
    if (destination?.attractions && destination.attractions.length > 0)
      return destination.attractions;
    return [];
  }, [propAttractions, destination]);

  const [stops, setStops] = useState<Point[]>([]);
  const [newStopName, setNewStopName] = useState("");
  const [attractionSearch, setAttractionSearch] = useState("");
  const [isSearchingAttractions, setIsSearchingAttractions] = useState(false);
  const [route, setRoute] = useState<Point[]>([]);
  const [summary, setSummary] = useState<string | null>(null);
  const [totalKm, setTotalKm] = useState<number | null>(null);
  const [roadKm, setRoadKm] = useState<number | null>(null);
  const [roadDurationMin, setRoadDurationMin] = useState<number | null>(null);
  const [roadGeometry, setRoadGeometry] = useState<[number, number][] | null>(null);
  const [routingServiceOffline, setRoutingServiceOffline] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Map container and Leaflet instances
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const routePolylineRef = useRef<L.Polyline | null>(null);
  const routeCasingRef = useRef<L.Polyline | null>(null);

  // Initialize stops
  useEffect(() => {
    if (initialPoints && initialPoints.length > 0) {
      setStops(initialPoints);
    } else if (destination?.lat && destination?.lon) {
      const initial: Point[] = [
        { name: destName, lat: destination.lat, lon: destination.lon },
      ];
      if (allAvailableAttractions.length > 0) {
        allAvailableAttractions.slice(0, 3).forEach((a: any) => {
          initial.push({
            name: a.name,
            lat: a.lat,
            lon: a.lon,
            category: a.category,
            rating: a.rating,
          });
        });
      }
      setStops(initial);
    } else if (destName) {
      setStops([{ name: destName }]);
    }
  }, [initialPoints, destination, destName, allAvailableAttractions]);

  const activePoints = route.length > 0 ? route : stops;

  useEffect(() => {
    if (onRouteStopsChange && activePoints.length > 0) {
      onRouteStopsChange(activePoints);
    }
  }, [activePoints, onRouteStopsChange]);

  const mappedPoints = useMemo(
    () =>
      activePoints.filter(
        (p) =>
          p.lat != null &&
          p.lon != null &&
          !isNaN(Number(p.lat)) &&
          !isNaN(Number(p.lon))
      ),
    [activePoints]
  );

  const unmappedStops = useMemo(
    () =>
      activePoints.filter(
        (p) =>
          p.lat == null ||
          p.lon == null ||
          isNaN(Number(p.lat)) ||
          isNaN(Number(p.lon))
      ),
    [activePoints]
  );

  // Fetch real road-following route geometry from OSRM
  const fetchRoadGeometry = useCallback(
    async (coords: [number, number][]) => {
      if (coords.length < 2) {
        setRoadGeometry(null);
        setRoadKm(null);
        setRoadDurationMin(null);
        setRoutingServiceOffline(false);
        return;
      }

      const locStr = coords.map(([lat, lon]) => `${lon},${lat}`).join(";");
      const url = `https://router.project-osrm.org/route/v1/driving/${locStr}?overview=full&geometries=geojson`;

      try {
        const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
        if (!res.ok) throw new Error(`OSRM HTTP ${res.status}`);
        const data = await res.json();

        if (data.code === "Ok" && data.routes && data.routes.length > 0) {
          const routeData = data.routes[0];
          const geojsonCoords = routeData.geometry?.coordinates || [];
          // Convert [lon, lat] from GeoJSON to [lat, lon] for Leaflet
          const leafletCoords: [number, number][] = geojsonCoords.map(
            (pt: [number, number]) => [pt[1], pt[0]]
          );
          setRoadGeometry(leafletCoords);
          setRoadKm(Math.round((routeData.distance / 1000) * 10) / 10);
          setRoadDurationMin(Math.round(routeData.duration / 60));
          setRoutingServiceOffline(false);
        } else {
          throw new Error("No driving route found");
        }
      } catch (err) {
        console.warn("[RouteOptimizer] OSRM road geometry lookup notice:", err);
        setRoadGeometry(null);
        setRoutingServiceOffline(true);
      }
    },
    []
  );

  // Update road geometry whenever mapped points change (if not already provided by optimizeRoute)
  useEffect(() => {
    if (mappedPoints.length >= 2) {
      const coords: [number, number][] = mappedPoints.map((p) => [
        Number(p.lat),
        Number(p.lon),
      ]);
      fetchRoadGeometry(coords);
    } else {
      setRoadGeometry(null);
      setRoadKm(null);
      setRoadDurationMin(null);
    }
  }, [mappedPoints, fetchRoadGeometry]);

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      // Default to destination coordinates or center of India
      const defaultCenter: [number, number] =
        destination?.lat && destination?.lon
          ? [Number(destination.lat), Number(destination.lon)]
          : [20.5937, 78.9629];

      const map = L.map(mapContainerRef.current, {
        center: defaultCenter,
        zoom: destination?.lat ? 12 : 5,
        zoomControl: true,
        scrollWheelZoom: true,
      });

      // Real OpenStreetMap Geographic Tiles (shows streets, roads, places, landmarks)
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(map);

      markersLayerRef.current = L.layerGroup().addTo(map);
      mapInstanceRef.current = map;

      // Invalidate size to guarantee full-width tile rendering
      setTimeout(() => {
        map.invalidateSize();
      }, 100);
    }

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
        markersLayerRef.current = null;
        routePolylineRef.current = null;
        routeCasingRef.current = null;
      }
    };
  }, []);

  // Custom marker pin factory
  const createMarkerIcon = (
    index: number,
    isStart: boolean,
    isEnd: boolean
  ) => {
    const bgColor = isStart ? "#10b981" : isEnd ? "#f43f5e" : "#0284c7";
    const label = index + 1;

    return L.divIcon({
      className: "custom-leaflet-marker",
      html: `
        <div style="
          position: relative;
          display: flex;
          flex-direction: column;
          align-items: center;
          transform: translate(-50%, -100%);
          cursor: pointer;
        ">
          <div style="
            background-color: ${bgColor};
            color: #ffffff;
            border: 2px solid #ffffff;
            border-radius: 9999px;
            width: 30px;
            height: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 13px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
            transition: transform 0.15s ease;
          ">
            ${label}
          </div>
          <div style="
            width: 0;
            height: 0;
            border-left: 6px solid transparent;
            border-right: 6px solid transparent;
            border-top: 7px solid ${bgColor};
            margin-top: -1px;
          "></div>
        </div>
      `,
      iconSize: [30, 36],
      iconAnchor: [15, 36],
      popupAnchor: [0, -36],
    });
  };

  // Sync Markers and Polyline on Map whenever active stops or road geometry change
  useEffect(() => {
    const map = mapInstanceRef.current;
    const markersLayer = markersLayerRef.current;
    if (!map || !markersLayer) return;

    // Clear previous markers
    markersLayer.clearLayers();

    // Remove existing polylines
    if (routePolylineRef.current) {
      routePolylineRef.current.remove();
      routePolylineRef.current = null;
    }
    if (routeCasingRef.current) {
      routeCasingRef.current.remove();
      routeCasingRef.current = null;
    }

    if (mappedPoints.length === 0) return;

    const bounds = L.latLngBounds([]);

    // 1. Add interactive numbered markers for each mapped stop
    mappedPoints.forEach((point, idx) => {
      const lat = Number(point.lat);
      const lon = Number(point.lon);
      const isStart = idx === 0;
      const isEnd = idx === mappedPoints.length - 1 && mappedPoints.length > 1;

      bounds.extend([lat, lon]);

      const icon = createMarkerIcon(idx, isStart, isEnd);
      const marker = L.marker([lat, lon], { icon });

      // Rich popup with attraction details and Google Maps directions link
      const roleLabel = isStart ? "Start Point" : isEnd ? "Final Destination" : `Stop #${idx + 1}`;
      const catText = point.category ? `• ${point.category}` : "";
      const ratingText = point.rating ? `• ${point.rating}★` : "";

      const popupContent = document.createElement("div");
      popupContent.className = "p-1 space-y-1.5 text-xs text-slate-800 font-sans";
      popupContent.innerHTML = `
        <div style="display:flex; align-items:center; gap:6px; margin-bottom:2px;">
          <span style="background:${isStart ? '#10b981' : isEnd ? '#f43f5e' : '#0284c7'}; color:#fff; font-size:10px; font-weight:700; padding:1px 6px; border-radius:4px;">
            ${roleLabel}
          </span>
          <span style="color:#64748b; font-size:11px;">${catText} ${ratingText}</span>
        </div>
        <h4 style="margin:0; font-size:14px; font-weight:700; color:#0f172a;">${point.name}</h4>
        <div style="font-family:monospace; font-size:10px; color:#64748b;">
          ${lat.toFixed(4)}°, ${lon.toFixed(4)}°
        </div>
        <div style="margin-top:6px; padding-top:6px; border-top:1px solid #e2e8f0;">
          <a href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
            point.name + `, ${destName}`
          )}" target="_blank" rel="noopener noreferrer" style="color:#2563eb; font-weight:600; text-decoration:none; display:inline-flex; align-items:center; gap:4px;">
            Open in Google Maps &rarr;
          </a>
        </div>
      `;

      marker.bindPopup(popupContent);
      markersLayer.addLayer(marker);
    });

    // 2. Render route polyline
    if (roadGeometry && roadGeometry.length > 1) {
      // Road-following route geometry from OSRM
      // Outer casing for high contrast on street maps
      routeCasingRef.current = L.polyline(roadGeometry, {
        color: "#ffffff",
        weight: 7,
        opacity: 0.85,
        lineCap: "round",
        lineJoin: "round",
      }).addTo(map);

      // Inner road-following polyline (Google Maps blue driving path)
      routePolylineRef.current = L.polyline(roadGeometry, {
        color: "#2563eb",
        weight: 4.5,
        opacity: 0.95,
        lineCap: "round",
        lineJoin: "round",
      }).addTo(map);

      // Extend bounds by road geometry
      roadGeometry.forEach(([lat, lon]) => bounds.extend([lat, lon]));
    } else if (mappedPoints.length > 1) {
      // Fallback straight connecting lines if routing service is offline
      const directCoords: [number, number][] = mappedPoints.map((p) => [
        Number(p.lat),
        Number(p.lon),
      ]);
      routePolylineRef.current = L.polyline(directCoords, {
        color: "#64748b",
        weight: 3,
        dashArray: "6, 8",
        opacity: 0.8,
      }).addTo(map);
    }

    // 3. Fit bounds smoothly
    if (bounds.isValid()) {
      map.fitBounds(bounds, {
        padding: [48, 48],
        maxZoom: 15,
      });
    }
  }, [mappedPoints, roadGeometry, destName]);

  const fitRouteBounds = () => {
    const map = mapInstanceRef.current;
    if (!map || mappedPoints.length === 0) return;
    const bounds = L.latLngBounds([]);
    if (roadGeometry && roadGeometry.length > 0) {
      roadGeometry.forEach(([lat, lon]) => bounds.extend([lat, lon]));
    } else {
      mappedPoints.forEach((p) =>
        bounds.extend([Number(p.lat), Number(p.lon)])
      );
    }
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [48, 48], maxZoom: 15 });
    }
  };

  // Google Maps Directions link generator
  const googleMapsDirectionsUrl = useMemo(() => {
    const validStops = (route.length > 0 ? route : stops).filter(
      (s) => s.name && s.name.trim()
    );
    if (validStops.length === 0) {
      return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
        destName
      )}`;
    }
    if (validStops.length === 1) {
      return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
        validStops[0].name + `, ${destName}`
      )}`;
    }
    const origin = validStops[0].name + `, ${destName}`;
    const destinationTarget =
      validStops[validStops.length - 1].name + `, ${destName}`;
    const waypoints = validStops
      .slice(1, -1)
      .map((s) => s.name + `, ${destName}`)
      .join("|");

    let url = `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(
      origin
    )}&destination=${encodeURIComponent(destinationTarget)}`;
    if (waypoints) {
      url += `&waypoints=${encodeURIComponent(waypoints)}`;
    }
    return url;
  }, [route, stops, destName]);

  const addCustomStop = () => {
    if (!newStopName.trim()) return;
    setStops((prev) => [...prev, { name: newStopName.trim() }]);
    setNewStopName("");
    setRoute([]);
    setSummary(null);
  };

  const addAttractionStop = (att: any) => {
    const exists = stops.some(
      (s) => s.name.toLowerCase() === att.name.toLowerCase()
    );
    if (exists) return;
    setStops((prev) => [
      ...prev,
      {
        name: att.name,
        lat: att.lat,
        lon: att.lon,
        category: att.category,
        rating: att.rating,
      },
    ]);
    setRoute([]);
    setSummary(null);
    setIsSearchingAttractions(false);
    setAttractionSearch("");
  };

  const removeStop = (idx: number) => {
    setStops((prev) => prev.filter((_, i) => i !== idx));
    setRoute([]);
    setSummary(null);
  };

  const moveStop = (idx: number, direction: "up" | "down") => {
    const targetIdx = direction === "up" ? idx - 1 : idx + 1;
    if (targetIdx < 0 || targetIdx >= stops.length) return;
    setStops((prev) => {
      const copy = [...prev];
      const temp = copy[idx];
      copy[idx] = copy[targetIdx];
      copy[targetIdx] = temp;
      return copy;
    });
    setRoute([]);
    setSummary(null);
  };

  const handleOptimize = async () => {
    if (stops.length === 0) return;
    setLoading(true);
    setError(null);

    try {
      const data = await optimizeRoute({
        points: stops,
        destination_name: destName,
      });
      const ordered = data.ordered_points || [];
      setRoute(ordered);
      setStops(ordered);
      setSummary(data.summary || null);
      setTotalKm(data.total_distance_km ?? null);

      if (data.road_distance_km != null) {
        setRoadKm(data.road_distance_km);
      }
      if (data.duration_min != null) {
        setRoadDurationMin(data.duration_min);
      }
      if (data.route_geometry && data.route_geometry.length > 0) {
        setRoadGeometry(data.route_geometry);
      }
    } catch (err: any) {
      console.error("Route optimization error:", err);
      setError("Failed to optimize route. Please check connection and retry.");
      setRoute([]);
    } finally {
      setLoading(false);
    }
  };

  const filteredAttractions = useMemo(() => {
    if (!attractionSearch.trim()) return allAvailableAttractions.slice(0, 8);
    return allAvailableAttractions
      .filter((a: any) =>
        a.name.toLowerCase().includes(attractionSearch.toLowerCase())
      )
      .slice(0, 8);
  }, [allAvailableAttractions, attractionSearch]);

  return (
    <div className="bg-card rounded-2xl p-6 shadow-sm border border-border/60 space-y-5">
      {/* Section Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2 text-foreground">
            <Compass className="h-5 w-5 text-coral" />
            <span>Interactive Geographic Route Map &amp; Optimizer</span>
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Real geographic street map powered by OpenStreetMap with road-following routing and heuristic sequence optimization.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <a
            href={googleMapsDirectionsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 bg-primary/10 hover:bg-primary/20 text-primary border border-primary/30 text-xs px-3 py-1.5 rounded-lg font-medium transition"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            <span>Open in Google Maps</span>
          </a>

          <Button
            onClick={handleOptimize}
            disabled={loading || stops.length === 0}
            size="sm"
            className="text-xs h-8 font-medium shadow-xs"
          >
            {loading ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                Optimizing Route...
              </>
            ) : (
              "Optimize Route Sequence"
            )}
          </Button>
        </div>
      </div>

      {/* PART A: Real Leaflet / OpenStreetMap Interactive Geographic Map */}
      <div className="relative rounded-2xl overflow-hidden border border-border/80 shadow-md bg-muted/20">
        {/* Floating Top Map Toolbar */}
        <div className="absolute top-3 left-3 z-[400] flex items-center gap-2 flex-wrap pointer-events-none">
          <div className="bg-background/95 backdrop-blur-md px-3 py-1.5 rounded-lg border border-border/70 shadow-sm text-xs flex items-center gap-2 pointer-events-auto">
            <Navigation className="h-3.5 w-3.5 text-primary" />
            <span className="font-semibold text-foreground text-xs truncate max-w-[160px]">
              {destName}
            </span>
            <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
              {mappedPoints.length} mapped stop{mappedPoints.length === 1 ? "" : "s"}
            </Badge>
          </div>

          {roadKm !== null && roadKm > 0 && (
            <div className="bg-background/95 backdrop-blur-md px-2.5 py-1.5 rounded-lg border border-border/70 shadow-sm text-xs flex items-center gap-1.5 pointer-events-auto text-emerald-600 dark:text-emerald-400 font-semibold">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>{roadKm} km driving</span>
              {roadDurationMin && (
                <span className="text-muted-foreground font-normal text-[11px]">
                  (~{roadDurationMin} min)
                </span>
              )}
            </div>
          )}
        </div>

        {/* Fit Bounds Action */}
        <div className="absolute top-3 right-3 z-[400]">
          <button
            type="button"
            onClick={fitRouteBounds}
            className="bg-background/95 hover:bg-background text-foreground border border-border/70 shadow-sm h-8 px-2.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition"
            title="Recenter and fit all route stops"
          >
            <RotateCcw className="h-3 w-3 text-primary" />
            <span className="hidden sm:inline">Fit Route</span>
          </button>
        </div>

        {/* Real Leaflet Map Viewport Container */}
        <div
          ref={mapContainerRef}
          className="w-full h-[420px] sm:h-[470px] z-0 focus:outline-none"
          tabIndex={0}
          aria-label={`Interactive map of ${destName}`}
        />

        {/* Bottom Legend Bar */}
        <div className="bg-background/90 backdrop-blur-sm border-t border-border/60 px-4 py-2 flex items-center justify-between flex-wrap gap-2 text-[11px] text-muted-foreground z-10 relative">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 font-medium text-foreground">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 inline-block border border-white" />
              Start Point (1)
            </span>
            {mappedPoints.length > 2 && (
              <span className="flex items-center gap-1.5 font-medium text-foreground">
                <span className="h-2.5 w-2.5 rounded-full bg-sky-500 inline-block border border-white" />
                Stops (2..{mappedPoints.length - 1})
              </span>
            )}
            {mappedPoints.length > 1 && (
              <span className="flex items-center gap-1.5 font-medium text-foreground">
                <span className="h-2.5 w-2.5 rounded-full bg-rose-500 inline-block border border-white" />
                Final Destination ({mappedPoints.length})
              </span>
            )}
          </div>

          <span className="text-[10px] italic text-muted-foreground">
            {roadGeometry
              ? "Road geometry follows actual streets via OpenStreetMap"
              : routingServiceOffline
              ? "Routing service offline; showing straight connections"
              : "Click any marker to view attraction info and directions"}
          </span>
        </div>
      </div>

      {/* PART B: Unmapped Stops Warning (Never fabricate coordinates) */}
      {unmappedStops.length > 0 && (
        <div className="p-3 bg-amber-500/10 border border-amber-500/30 text-amber-900 dark:text-amber-200 rounded-xl text-xs flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
            <span>
              <strong>Unmapped stops:</strong>{" "}
              {unmappedStops.map((s) => s.name).join(", ")} do not have verified coordinates in our database. They are preserved in your ordered sequence below but not plotted on the map.
            </span>
          </div>
        </div>
      )}

      {/* PART C: Summary Banner */}
      {summary && (
        <div className="p-3.5 bg-primary/5 rounded-xl border border-primary/20 text-xs text-foreground font-medium flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <Compass className="h-4 w-4 text-primary shrink-0" />
            <span>{summary}</span>
          </div>
          {roadKm != null ? (
            <Badge variant="default" className="text-xs shrink-0 font-semibold bg-emerald-600">
              {roadKm} km road driving
            </Badge>
          ) : (
            totalKm != null && totalKm > 0 && (
              <Badge variant="secondary" className="text-xs shrink-0 font-semibold">
                {totalKm.toFixed(1)} km proxy
              </Badge>
            )
          )}
        </div>
      )}

      {/* PART D: Route Controls Directly Underneath the Map */}
      <div className="space-y-4">
        {/* Add Stops: Custom input + Attraction selector */}
        <div className="space-y-2.5">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <span className="text-xs font-semibold text-foreground">
              Add Route Stops ({stops.length} selected)
            </span>
            {allAvailableAttractions.length > 0 && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setIsSearchingAttractions(!isSearchingAttractions)}
                className="text-xs h-7 text-primary hover:text-primary font-medium"
              >
                <Search className="h-3.5 w-3.5 mr-1" />
                {isSearchingAttractions ? "Close Attractions" : "Pick from Attractions"}
              </Button>
            )}
          </div>

          {/* Attraction picker drawer/search */}
          {isSearchingAttractions && allAvailableAttractions.length > 0 && (
            <div className="p-3.5 bg-muted/40 rounded-xl border border-border/60 space-y-2.5 animate-fade-up">
              <div className="flex items-center gap-2">
                <Input
                  placeholder={`Search attractions in ${destName}...`}
                  value={attractionSearch}
                  onChange={(e) => setAttractionSearch(e.target.value)}
                  className="text-xs h-8"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2 max-h-48 overflow-y-auto pt-1">
                {filteredAttractions.map((att: any, i: number) => {
                  const isAdded = stops.some(
                    (s) => s.name.toLowerCase() === att.name.toLowerCase()
                  );
                  return (
                    <button
                      key={i}
                      type="button"
                      disabled={isAdded}
                      onClick={() => addAttractionStop(att)}
                      className={`p-2 rounded-lg border text-left text-xs transition flex flex-col justify-between ${
                        isAdded
                          ? "bg-muted/80 opacity-60 border-border cursor-not-allowed"
                          : "bg-background hover:border-primary/50 hover:bg-primary/5 border-border shadow-2xs"
                      }`}
                    >
                      <span className="font-semibold truncate block">{att.name}</span>
                      <span className="text-[10px] text-muted-foreground mt-0.5">
                        {att.category || "Attraction"} • {att.rating ? `${att.rating}★` : "Verified"}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Custom stop input */}
          <div className="flex items-center gap-2 flex-wrap">
            <Input
              placeholder="Add custom stop (e.g. Airport, Hotel, Old Market)..."
              value={newStopName}
              onChange={(e) => setNewStopName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addCustomStop()}
              className="text-xs h-9 flex-1 min-w-[220px]"
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={addCustomStop}
              className="text-xs h-9 font-medium"
            >
              <Plus className="h-3.5 w-3.5 mr-1" /> Add Custom Stop
            </Button>
          </div>
        </div>

        {error && (
          <div className="flex items-center justify-between rounded-xl bg-destructive/10 text-destructive text-xs p-3">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleOptimize}
              className="text-xs h-7 px-2"
            >
              <RefreshCcw className="h-3 w-3 mr-1" /> Retry
            </Button>
          </div>
        )}

        {/* Ordered Stops List with Reordering Controls */}
        <div className="space-y-2 pt-1">
          <div className="flex items-center justify-between text-xs text-muted-foreground font-medium">
            <span>Ordered Stops Sequence</span>
            <span>Use arrows to reorder stops or click Optimize Route Sequence</span>
          </div>

          <div className="space-y-2">
            {stops.map((stop, idx) => {
              const hasCoords = stop.lat != null && stop.lon != null;
              const isStart = idx === 0;
              const isEnd = idx === stops.length - 1 && stops.length > 1;

              return (
                <div
                  key={idx}
                  className="p-3 bg-muted/40 rounded-xl border border-border/40 text-xs flex items-center justify-between gap-3 text-foreground"
                >
                  <div className="flex items-center gap-2.5 min-w-0 flex-1">
                    <div
                      className={`h-6 w-6 rounded-full flex items-center justify-center font-bold text-[11px] shrink-0 text-white ${
                        isStart
                          ? "bg-emerald-600"
                          : isEnd
                          ? "bg-rose-600"
                          : "bg-primary"
                      }`}
                    >
                      {idx + 1}
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold truncate">{stop.name}</span>
                        {isStart && (
                          <Badge variant="outline" className="text-[10px] py-0 px-1.5 border-emerald-500/40 text-emerald-600 dark:text-emerald-400">
                            Start
                          </Badge>
                        )}
                        {isEnd && (
                          <Badge variant="outline" className="text-[10px] py-0 px-1.5 border-rose-500/40 text-rose-600 dark:text-rose-400">
                            End
                          </Badge>
                        )}
                      </div>
                      <div className="text-[10px] text-muted-foreground flex items-center gap-1.5 mt-0.5">
                        {hasCoords ? (
                          <span className="font-mono text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                            <MapPin className="h-2.5 w-2.5" />
                            {Number(stop.lat).toFixed(4)}°, {Number(stop.lon).toFixed(4)}°
                          </span>
                        ) : (
                          <span className="text-amber-600 dark:text-amber-400 italic">
                            Unmapped coordinates
                          </span>
                        )}
                        {stop.category && <span>• {stop.category}</span>}
                      </div>
                    </div>
                  </div>

                  {/* Actions: Move Up, Move Down, Remove */}
                  <div className="flex items-center gap-1 shrink-0">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={idx === 0}
                      onClick={() => moveStop(idx, "up")}
                      className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                      title="Move stop earlier in route"
                    >
                      <ArrowUp className="h-3.5 w-3.5" />
                    </Button>

                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={idx === stops.length - 1}
                      onClick={() => moveStop(idx, "down")}
                      className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                      title="Move stop later in route"
                    >
                      <ArrowDown className="h-3.5 w-3.5" />
                    </Button>

                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => removeStop(idx)}
                      className="h-7 w-7 p-0 text-destructive/80 hover:text-destructive hover:bg-destructive/10"
                      title="Remove stop"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
