import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Building2,
  Plus,
  Loader2,
  TrendingUp,
  Clock,
  Wallet,
  Star,
  BedDouble,
  Briefcase,
  CheckCircle2,
  Circle,
  PackageOpen,
  CalendarX2,
  ArrowRight,
  CalendarCheck,
  Sparkles,
} from "lucide-react";
import {
  getMyPartnerProfile,
  getMyListings,
  createListing,
  getPartnerBookings,
  updateBookingStatus,
  getPartnerAnalytics,
  getDestinationsList,
  ListingPayload,
} from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

const STATUS_OPTIONS = ["Pending Payment", "Confirmed", "Cancelled", "Completed"];

const emptyForm: ListingPayload & { listing_type: "hotel" | "package" } = {
  listing_type: "hotel",
  destination_id: 0,
  name: "",
  category: "",
  price_tier: "medium",
  price: undefined,
  rating: undefined,
  amenities: [],
  description: "",
  thumbnail_url: "",
  photos: [],
  extra: {},
};

const PartnerDashboard = () => {
  const navigate = useNavigate();
  const { toast } = useToast();

  const [loading, setLoading] = useState(true);
  const [partner, setPartner] = useState<any>(null);
  const [listings, setListings] = useState<any[]>([]);
  const [bookings, setBookings] = useState<any[]>([]);
  const [analytics, setAnalytics] = useState<any>(null);
  const [destinations, setDestinations] = useState<any[]>([]);

  const [activeTab, setActiveTab] = useState("overview");
  const [showAddForm, setShowAddForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);

  const loadAll = async () => {
    const [listingsRes, bookingsRes, analyticsRes] = await Promise.all([
      getMyListings(),
      getPartnerBookings(),
      getPartnerAnalytics(),
    ]);
    setListings(listingsRes);
    setBookings(bookingsRes);
    setAnalytics(analyticsRes);
  };

  useEffect(() => {
    const token = localStorage.getItem("travelmate_token");
    if (!token) {
      navigate("/partner/login");
      return;
    }
    const role = localStorage.getItem("travelmate_role");
    if (role && role !== "partner" && role !== "admin") {
      navigate("/partner/register");
      return;
    }

    getMyPartnerProfile()
      .then((p) => {
        if (!p) {
          navigate("/partner/register");
          return;
        }
        setPartner(p);
        return loadAll();
      })
      .catch((err) => {
        // 401 means not logged in or session expired → send to partner login
        if (err?.message === "401") {
          navigate("/partner/login");
        } else {
          navigate("/partner/register");
        }
      })
      .finally(() => setLoading(false));

    getDestinationsList().then(setDestinations).catch(() => setDestinations([]));
  }, []);

  const update = (field: string, value: any) => setForm((f) => ({ ...f, [field]: value }));

  const handleCreateListing = async () => {
    if (!form.name.trim() || !form.destination_id) {
      toast({ title: "Missing details", description: "Name and destination are required.", variant: "destructive" });
      return;
    }
    setSubmitting(true);
    try {
      await createListing(form.listing_type, form);
      toast({ title: "Listing created" });
      setShowAddForm(false);
      setForm({ ...emptyForm, listing_type: form.listing_type });
      await loadAll();
    } catch (e: any) {
      toast({ title: "Failed to create listing", description: e.message, variant: "destructive" });
    }
    setSubmitting(false);
  };

  const handleStatusChange = async (reference: string, status: string) => {
    try {
      await updateBookingStatus(reference, status);
      toast({ title: "Booking updated" });
      const b = await getPartnerBookings();
      setBookings(b);
      const a = await getPartnerAnalytics();
      setAnalytics(a);
    } catch (e: any) {
      toast({ title: "Failed to update status", description: e.message, variant: "destructive" });
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!partner) return null;

  return (
    <div className="min-h-screen container mx-auto px-6 max-w-5xl py-16">
      <div className="flex items-center justify-between flex-wrap gap-4 mb-6">
        <div className="flex items-center gap-3">
          <div className="h-12 w-12 rounded-full bg-primary/15 flex items-center justify-center">
            <Building2 className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">{partner.business_name}</h1>
            <p className="text-sm text-muted-foreground capitalize">
              {partner.partner_type.replace("_", " ")} Partner
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="hero"
            size="sm"
            onClick={() => {
              setActiveTab("listings");
              setShowAddForm(true);
            }}
          >
            <Plus className="h-4 w-4 mr-1.5" /> Add Listing
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="mb-6 bg-muted/60">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="listings">Listings</TabsTrigger>
          <TabsTrigger value="bookings">Bookings</TabsTrigger>
        </TabsList>

        {/* Overview / Analytics */}
        <TabsContent value="overview" className="animate-fade-up">
          {/* Quick Actions */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
            <Button
              variant="outline"
              className="h-auto py-3 px-4 flex items-center justify-between bg-card/95 border-white/20 hover:border-primary/50 text-left"
              onClick={() => {
                setForm({ ...emptyForm, listing_type: "hotel" });
                setActiveTab("listings");
                setShowAddForm(true);
              }}
            >
              <div className="flex items-center gap-2.5">
                <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary shrink-0">
                  <BedDouble className="h-4 w-4" />
                </div>
                <div>
                  <p className="font-semibold text-xs text-foreground">Add Stay</p>
                  <p className="text-[11px] text-muted-foreground">Hotel, resort or stay</p>
                </div>
              </div>
              <ArrowRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            </Button>

            <Button
              variant="outline"
              className="h-auto py-3 px-4 flex items-center justify-between bg-card/95 border-white/20 hover:border-coral/50 text-left"
              onClick={() => {
                setForm({ ...emptyForm, listing_type: "package" });
                setActiveTab("listings");
                setShowAddForm(true);
              }}
            >
              <div className="flex items-center gap-2.5">
                <div className="h-8 w-8 rounded-lg bg-coral/10 flex items-center justify-center text-coral shrink-0">
                  <Briefcase className="h-4 w-4" />
                </div>
                <div>
                  <p className="font-semibold text-xs text-foreground">Add Package</p>
                  <p className="text-[11px] text-muted-foreground">Tour or travel experience</p>
                </div>
              </div>
              <ArrowRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            </Button>

            <Button
              variant="outline"
              className="h-auto py-3 px-4 flex items-center justify-between bg-card/95 border-white/20 hover:border-white/40 text-left"
              onClick={() => setActiveTab("bookings")}
            >
              <div className="flex items-center gap-2.5">
                <div className="h-8 w-8 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-600 dark:text-emerald-400 shrink-0">
                  <CalendarCheck className="h-4 w-4" />
                </div>
                <div>
                  <p className="font-semibold text-xs text-foreground">View Bookings</p>
                  <p className="text-[11px] text-muted-foreground">{bookings.length} reservation{bookings.length === 1 ? "" : "s"}</p>
                </div>
              </div>
              <ArrowRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            </Button>
          </div>

          {/* Onboarding Checklist for New Partners */}
          {listings.length === 0 && (
            <Card className="p-5 mb-6 bg-gradient-to-br from-primary/5 via-card to-card border border-primary/20">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold flex items-center gap-2 text-foreground">
                  <Sparkles className="h-4 w-4 text-primary" /> Partner Onboarding Checklist
                </h3>
                <Badge variant="outline" className="text-xs bg-primary/10 border-primary/30 text-primary">
                  1 of 3 Complete
                </Badge>
              </div>
              <div className="space-y-2.5">
                <div className="flex items-start gap-3 p-2.5 rounded-lg bg-muted/40 border border-border/40">
                  <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs font-semibold text-foreground">Step 1: Partner profile registered</p>
                    <p className="text-[11px] text-muted-foreground">
                      Business profile created for {partner.business_name} ({partner.partner_type.replace("_", " ")} partner)
                    </p>
                  </div>
                </div>

                <div className="flex items-start justify-between gap-3 p-2.5 rounded-lg bg-muted/40 border border-primary/30">
                  <div className="flex items-start gap-3">
                    <Circle className="h-5 w-5 text-muted-foreground shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs font-semibold text-foreground">Step 2: Add your first listing</p>
                      <p className="text-[11px] text-muted-foreground">
                        Publish your stays or packages to make them discoverable by AI travel recommendations.
                      </p>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="hero"
                    className="text-xs h-7 px-3 shrink-0"
                    onClick={() => {
                      setActiveTab("listings");
                      setShowAddForm(true);
                    }}
                  >
                    Add Listing
                  </Button>
                </div>

                <div className="flex items-start gap-3 p-2.5 rounded-lg bg-muted/20 border border-border/30 opacity-75">
                  <Circle className="h-5 w-5 text-muted-foreground shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs font-semibold text-foreground">Step 3: Receive traveler bookings</p>
                    <p className="text-[11px] text-muted-foreground">
                      Guest bookings will appear in your Bookings tab once travelers select your listings.
                    </p>
                  </div>
                </div>
              </div>
            </Card>
          )}

          {analytics && (
            <div className="grid sm:grid-cols-3 gap-4 mb-6">
              <Card className="p-4 flex items-center gap-3 bg-card/95 border border-white/20">
                <TrendingUp className="h-6 w-6 text-primary" />
                <div>
                  <p className="text-xs text-muted-foreground">Total Bookings</p>
                  <p className="text-xl font-bold">{analytics.total_bookings}</p>
                </div>
              </Card>
              <Card className="p-4 flex items-center gap-3 bg-card/95 border border-white/20">
                <Clock className="h-6 w-6 text-amber-500" />
                <div>
                  <p className="text-xs text-muted-foreground">Pending Bookings</p>
                  <p className="text-xl font-bold">{analytics.pending_bookings}</p>
                </div>
              </Card>
              <Card className="p-4 flex items-center gap-3 bg-card/95 border border-white/20">
                <Wallet className="h-6 w-6 text-green-600" />
                <div>
                  <p className="text-xs text-muted-foreground">Revenue Estimate</p>
                  <p className="text-xl font-bold">₹{Number(analytics.revenue_estimate).toLocaleString()}</p>
                </div>
              </Card>
            </div>
          )}

          <Card className="p-5 bg-card/95 border border-white/20">
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <Star className="h-4 w-4 text-coral" /> Popular Listings
            </h3>
            {analytics?.popular_listings?.length > 0 ? (
              <div className="space-y-2">
                {analytics.popular_listings.map((l: any) => (
                  <div key={l.name} className="flex items-center justify-between text-sm bg-muted/40 rounded-lg px-3 py-2">
                    <span>{l.name}</span>
                    <Badge variant="outline">{l.bookings} bookings</Badge>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No bookings yet.</p>
            )}
          </Card>
        </TabsContent>

        {/* Listings */}
        <TabsContent value="listings" className="animate-fade-up">
          <div className="flex justify-end mb-4">
            <Button variant="hero" size="sm" onClick={() => setShowAddForm((s) => !s)}>
              <Plus className="h-4 w-4 mr-1" /> Add Listing
            </Button>
          </div>

          {showAddForm && (
            <Card className="p-5 mb-5 bg-card/95 border border-white/20 space-y-4">
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <Label>Listing type</Label>
                  <Select value={form.listing_type} onValueChange={(v: "hotel" | "package") => update("listing_type", v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="hotel">Stay (Hotel / Homestay / Resort)</SelectItem>
                      <SelectItem value="package">Package (Tour / Experience)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Destination</Label>
                  <Select
                    value={form.destination_id ? String(form.destination_id) : ""}
                    onValueChange={(v) => update("destination_id", Number(v))}
                  >
                    <SelectTrigger><SelectValue placeholder="Select destination" /></SelectTrigger>
                    <SelectContent>
                      {destinations.map((d) => (
                        <SelectItem key={d.id} value={String(d.id)}>{d.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div>
                <Label>{form.listing_type === "hotel" ? "Hotel name" : "Package title"}</Label>
                <Input value={form.name} onChange={(e) => update("name", e.target.value)} />
              </div>

              <div className="grid sm:grid-cols-3 gap-4">
                <div>
                  <Label>{form.listing_type === "hotel" ? "Price / night (₹)" : "Price / package (₹)"}</Label>
                  <Input
                    type="number"
                    value={form.price ?? ""}
                    onChange={(e) => update("price", Number(e.target.value))}
                  />
                </div>
                <div>
                  <Label>Price tier</Label>
                  <Select value={form.price_tier} onValueChange={(v) => update("price_tier", v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">Low</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="luxury">Luxury</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Rating (0-5)</Label>
                  <Input
                    type="number"
                    step="0.1"
                    value={form.rating ?? ""}
                    onChange={(e) => update("rating", Number(e.target.value))}
                  />
                </div>
              </div>

              {form.listing_type === "package" && (
                <div className="grid sm:grid-cols-2 gap-4">
                  <div>
                    <Label>Duration (days)</Label>
                    <Input
                      type="number"
                      value={form.extra?.duration_days ?? ""}
                      onChange={(e) => update("extra", { ...form.extra, duration_days: Number(e.target.value) })}
                    />
                  </div>
                  <div>
                    <Label>Capacity (max travelers)</Label>
                    <Input
                      type="number"
                      value={form.extra?.capacity ?? ""}
                      onChange={(e) => update("extra", { ...form.extra, capacity: Number(e.target.value) })}
                    />
                  </div>
                </div>
              )}

              <div>
                <Label>Amenities / inclusions (comma-separated)</Label>
                <Input
                  value={(form.amenities || []).join(", ")}
                  onChange={(e) => update("amenities", e.target.value.split(",").map((s) => s.trim()).filter(Boolean))}
                  placeholder="wifi, breakfast, pool"
                />
              </div>

              <div>
                <Label>Description</Label>
                <Textarea
                  rows={3}
                  value={form.description}
                  onChange={(e) => update("description", e.target.value)}
                />
              </div>

              <div>
                <Label>Thumbnail image URL</Label>
                <Input
                  value={form.thumbnail_url}
                  onChange={(e) => update("thumbnail_url", e.target.value)}
                  placeholder="https://..."
                />
              </div>

              <Button variant="hero" className="w-full h-11" onClick={handleCreateListing} disabled={submitting}>
                {submitting ? "Saving..." : "Save Listing"}
              </Button>
            </Card>
          )}

          <div className="grid sm:grid-cols-2 gap-4">
            {listings.map((l) => (
              <Card key={`${l.listing_type}-${l.id}`} className="p-4 bg-card/95 border border-white/20">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    {l.listing_type === "hotel" ? (
                      <BedDouble className="h-4 w-4 text-primary" />
                    ) : (
                      <Briefcase className="h-4 w-4 text-coral" />
                    )}
                    <h4 className="font-semibold">{l.name}</h4>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-[10px] bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 font-medium">
                      Active
                    </Badge>
                    {l.rating && (
                      <span className="text-xs flex items-center gap-1">
                        <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" /> {l.rating}
                      </span>
                    )}
                  </div>
                </div>
                <p className="text-xs text-muted-foreground mb-2 capitalize">{l.category}</p>
                <p className="text-sm text-muted-foreground line-clamp-2 mb-2">{l.description}</p>
                <div className="flex flex-wrap gap-1">
                  {l.price && <Badge variant="outline">₹{l.price}</Badge>}
                  <Badge variant="outline" className="capitalize">{l.price_tier}</Badge>
                  {l.extra?.duration_days && <Badge variant="outline">{l.extra.duration_days} days</Badge>}
                </div>
              </Card>
            ))}
            {listings.length === 0 && !showAddForm && (
              <Card className="col-span-full p-8 text-center bg-card/95 border border-white/20 flex flex-col items-center justify-center space-y-3">
                <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                  <Plus className="h-6 w-6" />
                </div>
                <div>
                  <h4 className="font-semibold text-base">No listings created yet</h4>
                  <p className="text-xs text-muted-foreground max-w-sm mt-1">
                    Add your accommodations or travel packages so that TravelMate's AI recommendation engine can match them with travelers.
                  </p>
                </div>
                <Button variant="hero" size="sm" onClick={() => setShowAddForm(true)}>
                  <Plus className="h-4 w-4 mr-1.5" /> Create Your First Listing
                </Button>
              </Card>
            )}
          </div>
        </TabsContent>

        {/* Bookings */}
        <TabsContent value="bookings" className="animate-fade-up">
          <Card className="p-4 bg-card/95 border border-white/20 overflow-x-auto">
            {bookings.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Reference</TableHead>
                    <TableHead>Guest</TableHead>
                    <TableHead>Dates</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {bookings.map((b) => (
                    <TableRow key={b.booking_reference}>
                      <TableCell className="font-mono text-xs">{b.booking_reference}</TableCell>
                      <TableCell>
                        <p>{b.guest_name}</p>
                        <p className="text-xs text-muted-foreground">{b.guest_email}</p>
                      </TableCell>
                      <TableCell className="text-xs">
                        {b.check_in_date} → {b.check_out_date}
                      </TableCell>
                      <TableCell>{b.total_amount ? `₹${Number(b.total_amount).toLocaleString()}` : "—"}</TableCell>
                      <TableCell>
                        <Select value={b.status} onValueChange={(v) => handleStatusChange(b.booking_reference, v)}>
                          <SelectTrigger className="h-8 w-36">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {STATUS_OPTIONS.map((s) => (
                              <SelectItem key={s} value={s} disabled={s === "Pending Payment"}>
                                {s}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="p-8 text-center flex flex-col items-center justify-center space-y-3">
                <div className="h-12 w-12 rounded-full bg-muted/60 flex items-center justify-center text-muted-foreground">
                  <Clock className="h-6 w-6" />
                </div>
                <div>
                  <h4 className="font-semibold text-base">No bookings received yet</h4>
                  <p className="text-xs text-muted-foreground max-w-md mt-1">
                    Once travelers reserve your accommodations or packages, reservation details, guest information, and payment statuses will appear here in real time.
                  </p>
                </div>
                {listings.length === 0 && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-xs mt-2"
                    onClick={() => {
                      setActiveTab("listings");
                      setShowAddForm(true);
                    }}
                  >
                    <Plus className="h-3.5 w-3.5 mr-1.5" /> Publish Your First Listing
                  </Button>
                )}
              </div>
            )}
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default PartnerDashboard;
