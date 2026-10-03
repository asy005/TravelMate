import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  MapPin,
  Cloud,
  Backpack,
  Wallet,
  Route as RouteIcon,
  Lightbulb,
  Star,
  CheckCircle2,
  Compass,
  CalendarDays,
  Users,
  Sparkles,
  BedDouble,
  AlertTriangle,
  Briefcase,
} from "lucide-react";

interface TripDashboardProps {
  plan: Record<string, any>;
  sessionId?: string | null;
}

const SECTION_STAGGER_MS = 60;

export const TripDashboard = ({ plan, sessionId }: TripDashboardProps) => {
  const navigate = useNavigate();
  const [checkedItems, setCheckedItems] = useState<Record<string, boolean>>({});

  const overview = plan.trip_overview || {};
  const destinations = plan.destinations || [];
  const itinerary = plan.day_wise_itinerary || [];
  const budget = plan.budget;
  const packing: string[] = plan.packing_list || [];
  const nearby: any[] = plan.nearby_attractions || [];
  const tips: string[] = plan.travel_tips || [];
  const route = plan.route;

  const primaryDest = destinations[0];
  const selectedHotel = destinations.find((d: any) => d.selected_hotel)?.selected_hotel;
  const selectedHotelDestId = destinations.find((d: any) => d.selected_hotel)?.id;
  const selectedPackage = destinations.find((d: any) => d.selected_package)?.selected_package;
  const selectedPackageDestId = destinations.find((d: any) => d.selected_package)?.id;

  const goToHotel = (hotelId: number, destinationId: number) => {
    const params = new URLSearchParams();
    if (sessionId) params.set("session_id", sessionId);
    params.set("destination_id", String(destinationId));
    navigate(`/hotel/${hotelId}?${params.toString()}`);
  };

  const goToPackage = (packageId: number, destinationId: number) => {
    const params = new URLSearchParams();
    if (sessionId) params.set("session_id", sessionId);
    params.set("destination_id", String(destinationId));
    navigate(`/package/${packageId}?${params.toString()}`);
  };

  const packedCount = packing.filter((item) => checkedItems[item]).length;
  const packingPercent = packing.length > 0 ? Math.round((packedCount / packing.length) * 100) : 0;

  return (
    <div className="space-y-6 animate-fade-up">
      {/* ---- Trip Overview header ---- */}
      <Card className="p-6 bg-gradient-to-br from-primary/10 via-card to-coral/5 border border-white/20">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1 flex items-center gap-1">
              <Sparkles className="h-3.5 w-3.5 text-coral" /> Your AI Journey Dashboard
            </p>
            <h2 className="text-3xl font-bold">
              Trip to {overview.primary_destination || "your destination"}
            </h2>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 mt-4">
          {overview.duration_days && (
            <Badge variant="outline" className="flex items-center gap-1 font-normal">
              <CalendarDays className="h-3 w-3" /> {overview.duration_days} days
            </Badge>
          )}
          {overview.travelers && (
            <Badge variant="outline" className="flex items-center gap-1 font-normal">
              <Users className="h-3 w-3" /> {overview.travelers} traveler{overview.travelers > 1 ? "s" : ""}
            </Badge>
          )}
          {overview.budget && (
            <Badge variant="outline" className="flex items-center gap-1 font-normal">
              <Wallet className="h-3 w-3" /> {overview.budget} budget
            </Badge>
          )}
          {overview.travel_style && (
            <Badge variant="outline" className="flex items-center gap-1 font-normal capitalize">
              <Compass className="h-3 w-3" /> {overview.travel_style}
            </Badge>
          )}
        </div>

        {primaryDest?.explanation && (
          <>
            <Separator className="my-4" />
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">
                Why we picked {primaryDest.name}
              </p>
              <p className="text-sm leading-relaxed">{primaryDest.explanation}</p>
            </div>
          </>
        )}
      </Card>

      {/* ---- Selected hotel (or prompt to pick one) ---- */}
      {selectedHotel ? (
        <Card className="p-4 bg-card/95 backdrop-blur-md border border-primary/30 flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-primary/15 flex items-center justify-center">
              <BedDouble className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3 text-primary" /> Selected stay
              </p>
              <p className="font-semibold">{selectedHotel.name}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">
              {selectedHotel.price_per_night ? `₹${selectedHotel.price_per_night}/night` : ""}
              {selectedHotel.star_rating ? ` · ${selectedHotel.star_rating}★` : ""}
            </span>
            <Button
              size="sm"
              variant="hero"
              onClick={() => {
                const params = new URLSearchParams();
                if (sessionId) params.set("session_id", sessionId);
                if (selectedHotelDestId) params.set("destination_id", String(selectedHotelDestId));
                navigate(`/booking/${selectedHotel.id}?${params.toString()}`);
              }}
            >
              Book Now
            </Button>
          </div>
        </Card>
      ) : (
        primaryDest?.recommended_hotels?.length > 0 && (
          <Card className="p-4 bg-muted/30 border border-white/10">
            <p className="text-sm text-muted-foreground mb-2">
              No hotel selected yet — pick one to complete your dashboard.
            </p>
            <div className="flex flex-wrap gap-2">
              {primaryDest.recommended_hotels.map((hotel: any) => (
                <button
                  key={hotel.id}
                  onClick={() => goToHotel(hotel.id, primaryDest.id)}
                  className="text-xs bg-card hover:bg-muted transition-colors rounded-lg px-3 py-2 border border-white/10"
                >
                  {hotel.name}
                  {hotel.price_per_night ? ` · ₹${hotel.price_per_night}/night` : ""}
                </button>
              ))}
            </div>
          </Card>
        )
      )}

      {/* ---- Selected package (or prompt to pick one) ---- */}
      {selectedPackage ? (
        <Card className="p-4 bg-card/95 backdrop-blur-md border border-coral/30 flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-coral/15 flex items-center justify-center">
              <Briefcase className="h-5 w-5 text-coral" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3 text-coral" /> Selected package
              </p>
              <p className="font-semibold">{selectedPackage.title}</p>
              {selectedPackage.partner_name && (
                <p className="text-xs text-muted-foreground">by {selectedPackage.partner_name}</p>
              )}
            </div>
          </div>
          <span className="text-sm text-muted-foreground">
            {selectedPackage.price_per_package ? `₹${selectedPackage.price_per_package}/package` : ""}
            {selectedPackage.duration_days ? ` · ${selectedPackage.duration_days} days` : ""}
          </span>
        </Card>
      ) : (
        primaryDest?.recommended_packages?.length > 0 && (
          <Card className="p-4 bg-muted/30 border border-white/10">
            <p className="text-sm text-muted-foreground mb-2 flex items-center gap-1">
              <Briefcase className="h-3.5 w-3.5" /> Tour packages available for this trip
            </p>
            <div className="flex flex-wrap gap-2">
              {primaryDest.recommended_packages.map((pkg: any) => (
                <button
                  key={pkg.id}
                  onClick={() => goToPackage(pkg.id, primaryDest.id)}
                  className="text-xs bg-card hover:bg-muted transition-colors rounded-lg px-3 py-2 border border-white/10"
                >
                  {pkg.title}
                  {pkg.price_per_package ? ` · ₹${pkg.price_per_package}` : ""}
                  {pkg.duration_days ? ` · ${pkg.duration_days}d` : ""}
                </button>
              ))}
            </div>
          </Card>
        )
      )}

      {/* ---- Unified tabbed dashboard ---- */}
      <Card className="p-4 sm:p-6 bg-card/95 backdrop-blur-md border border-white/20">
        <Tabs defaultValue="itinerary" className="w-full">
          <TabsList className="flex flex-wrap h-auto gap-1 bg-muted/60 mb-4">
            <TabsTrigger value="itinerary">Itinerary</TabsTrigger>
            <TabsTrigger value="budget">Budget</TabsTrigger>
            <TabsTrigger value="weather">Weather</TabsTrigger>
            <TabsTrigger value="packing">Packing</TabsTrigger>
            <TabsTrigger value="nearby">Nearby</TabsTrigger>
            <TabsTrigger value="route">Route</TabsTrigger>
          </TabsList>

          {/* Itinerary */}
          <TabsContent value="itinerary" className="animate-fade-up">
            {itinerary.length > 0 ? (
              <div className="space-y-2">
                {itinerary.map((day: any, i: number) => (
                  <div
                    key={day.day}
                    style={{ animationDelay: `${i * SECTION_STAGGER_MS}ms` }}
                    className="flex gap-3 items-start bg-muted/40 rounded-xl p-3 border border-white/10 animate-fade-up"
                  >
                    <Badge className="shrink-0">Day {day.day}</Badge>
                    <p className="text-sm">{day.summary}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No itinerary generated yet.</p>
            )}

            {tips.length > 0 && (
              <>
                <Separator className="my-4" />
                <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                  <Lightbulb className="h-4 w-4 text-coral" /> Travel Tips
                </h4>
                <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                  {tips.map((tip: string, i: number) => (
                    <li key={i}>{tip}</li>
                  ))}
                </ul>
              </>
            )}
          </TabsContent>

          {/* Budget */}
          <TabsContent value="budget" className="animate-fade-up">
            {budget ? (
              <>
                <div className="flex items-center justify-between flex-wrap gap-2 mb-4">
                  <Badge
                    className={
                      budget.status === "Within Budget"
                        ? "bg-green-600 hover:bg-green-600"
                        : budget.status === "Near Budget Limit"
                        ? "bg-amber-500 hover:bg-amber-500"
                        : "bg-destructive hover:bg-destructive"
                    }
                  >
                    {budget.status === "Within Budget" && <CheckCircle2 className="h-3 w-3 mr-1" />}
                    {budget.status === "Near Budget Limit" && <AlertTriangle className="h-3 w-3 mr-1" />}
                    {budget.status === "Over Budget" && <AlertTriangle className="h-3 w-3 mr-1" />}
                    {budget.status}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    Total budget: ₹{Number(budget.total_budget).toLocaleString()}
                    {budget.budget_source === "implied" ? " (estimated from tier)" : ""}
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm mb-4">
                  {Object.entries(budget.breakdown || {}).map(([key, value]) => (
                    <div
                      key={key}
                      className="bg-muted/40 rounded-xl p-3 border border-white/10 text-center"
                    >
                      <p className="text-muted-foreground capitalize text-xs mb-1">
                        {key.replace("_", " ")}
                      </p>
                      <p className="font-semibold">₹{Number(value).toLocaleString()}</p>
                    </div>
                  ))}
                </div>

                <div className="grid sm:grid-cols-3 gap-3 mb-4">
                  <div className="flex items-center justify-between bg-primary/10 rounded-xl p-4">
                    <span className="text-sm font-medium">Estimated total</span>
                    <span className="text-lg font-bold">
                      ₹{Number(budget.estimated_total).toLocaleString()}
                    </span>
                  </div>
                  <div className="flex items-center justify-between bg-muted/40 rounded-xl p-4 border border-white/10">
                    <span className="text-sm">Per traveler</span>
                    <span className="font-semibold">
                      ₹{Number(budget.cost_per_traveler).toLocaleString()}
                    </span>
                  </div>
                  <div className="flex items-center justify-between bg-muted/40 rounded-xl p-4 border border-white/10">
                    <span className="text-sm">Per day</span>
                    <span className="font-semibold">
                      ₹{Number(budget.cost_per_day).toLocaleString()}
                    </span>
                  </div>
                </div>

                <div
                  className={`flex items-center justify-between rounded-xl p-3 text-sm ${
                    budget.remaining_budget < 0
                      ? "bg-destructive/10 text-destructive"
                      : "bg-green-500/10 text-green-700 dark:text-green-400"
                  }`}
                >
                  <span>{budget.remaining_budget < 0 ? "Over by" : "Remaining budget"}</span>
                  <span className="font-semibold">
                    ₹{Math.abs(Number(budget.remaining_budget)).toLocaleString()}
                  </span>
                </div>

                {budget.status === "Over Budget" && budget.alternative_hotels?.length > 0 && (
                  <>
                    <Separator className="my-4" />
                    <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-amber-500" /> This hotel puts you over budget — try instead:
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {budget.alternative_hotels.map((hotel: any) =>
                        primaryDest ? (
                          <button
                            key={hotel.id}
                            onClick={() => goToHotel(hotel.id, primaryDest.id)}
                            className="text-xs bg-card hover:bg-muted transition-colors rounded-lg px-3 py-2 border border-white/10"
                          >
                            {hotel.name}
                            {hotel.price_per_night ? ` · ₹${hotel.price_per_night}/night` : ""}
                          </button>
                        ) : null
                      )}
                    </div>
                  </>
                )}
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No budget estimate available.</p>
            )}
          </TabsContent>

          {/* Weather */}
          <TabsContent value="weather" className="animate-fade-up">
            {destinations.some((d: any) => d.weather) ? (
              <div className="grid sm:grid-cols-2 gap-3">
                {destinations.map((dest: any) =>
                  dest.weather ? (
                    <div
                      key={dest.id}
                      className="flex items-center justify-between bg-muted/40 rounded-xl p-3 border border-white/10"
                    >
                      <div className="flex items-center gap-2">
                        <Cloud className="h-4 w-4 text-sky" />
                        <span className="text-sm font-medium">{dest.name}</span>
                      </div>
                      <span className="text-sm text-muted-foreground">
                        {dest.weather.description}, {Math.round(dest.weather.temp)}°C
                      </span>
                    </div>
                  ) : null
                )}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Weather data isn't available right now.</p>
            )}
          </TabsContent>

          {/* Packing */}
          <TabsContent value="packing" className="animate-fade-up">
            {packing.length > 0 ? (
              <>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs text-muted-foreground">
                    {packedCount}/{packing.length} packed
                  </span>
                  <span className="text-xs font-semibold text-primary">{packingPercent}%</span>
                </div>
                <div className="grid sm:grid-cols-2 gap-2">
                  {packing.map((item) => (
                    <label
                      key={item}
                      className="flex items-center gap-2 bg-muted/40 rounded-lg px-3 py-2 border border-white/10 cursor-pointer"
                    >
                      <Checkbox
                        checked={!!checkedItems[item]}
                        onCheckedChange={(val) =>
                          setCheckedItems((prev) => ({ ...prev, [item]: !!val }))
                        }
                      />
                      <span
                        className={`text-sm ${checkedItems[item] ? "line-through text-muted-foreground" : ""}`}
                      >
                        {item}
                      </span>
                    </label>
                  ))}
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No packing list generated yet.</p>
            )}
          </TabsContent>

          {/* Nearby */}
          <TabsContent value="nearby" className="animate-fade-up">
            {nearby.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {nearby.map((a: any, i: number) => (
                  <Badge key={i} variant="outline" className="font-normal flex items-center gap-1">
                    <MapPin className="h-3 w-3" />
                    {a.name}
                    {a.distance_m ? ` · ${Math.round(a.distance_m)}m` : ""}
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No nearby attractions found for this destination yet.
              </p>
            )}
          </TabsContent>

          {/* Route */}
          <TabsContent value="route" className="animate-fade-up">
            {route ? (
              <div className="flex items-center gap-2 bg-muted/40 rounded-xl p-4 border border-white/10">
                <RouteIcon className="h-5 w-5 text-coral" />
                <p className="text-sm">
                  Approx. {route.distance_km} km, {route.eta_hours} hours by road.
                </p>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Add a starting location to see a route estimate.
              </p>
            )}
          </TabsContent>
        </Tabs>
      </Card>
    </div>
  );
};
