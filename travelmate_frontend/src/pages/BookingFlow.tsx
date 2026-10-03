import { useEffect, useState } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  ArrowLeft,
  ArrowRight,
  BedDouble,
  CalendarDays,
  Users,
  MessageSquare,
} from "lucide-react";
import { PageLoader } from "@/components/PageLoader";
import { getHotelDetails, createBooking, createPaymentOrder, verifyPayment } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

const STEPS = ["Guest Details", "Stay Details", "Review & Confirm"] as const;

const BookingFlow = () => {
  const { hotelId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { toast } = useToast();

  const destinationId = searchParams.get("destination_id");
  const sessionId = searchParams.get("session_id");

  const [hotel, setHotel] = useState<any>(null);
  const [loadingHotel, setLoadingHotel] = useState(true);
  const [step, setStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  const [form, setForm] = useState({
    guest_name: "",
    guest_email: "",
    guest_phone: "",
    check_in_date: "",
    check_out_date: "",
    num_rooms: 1,
    num_guests: 1,
    special_requests: "",
  });

  useEffect(() => {
    if (!hotelId) return;
    getHotelDetails(hotelId)
      .then(setHotel)
      .catch(() => setHotel(null))
      .finally(() => setLoadingHotel(false));
  }, [hotelId]);

  const update = (field: string, value: any) => setForm((f) => ({ ...f, [field]: value }));

  const nights =
    form.check_in_date && form.check_out_date
      ? Math.max(
          Math.round(
            (new Date(form.check_out_date).getTime() - new Date(form.check_in_date).getTime()) /
              (1000 * 60 * 60 * 24)
          ),
          0
        )
      : 0;

  const estimatedTotal = hotel?.price_per_night
    ? hotel.price_per_night * nights * (form.num_rooms || 1)
    : null;

  const isStep1Valid = form.guest_name.trim() && form.guest_email.trim() && form.guest_phone.trim();
  const isStep2Valid =
    form.check_in_date && form.check_out_date && nights > 0 && form.num_rooms >= 1 && form.num_guests >= 1;

  const handleNext = () => setStep((s) => Math.min(s + 1, STEPS.length - 1));
  const handleBack = () => (step === 0 ? navigate(-1) : setStep((s) => s - 1));

  const loadRazorpayScript = (): Promise<boolean> =>
    new Promise((resolve) => {
      if ((window as any).Razorpay) {
        resolve(true);
        return;
      }
      const script = document.createElement("script");
      script.src = "https://checkout.razorpay.com/v1/checkout.js";
      script.onload = () => resolve(true);
      script.onerror = () => resolve(false);
      document.body.appendChild(script);
    });

  const handleConfirm = async () => {
    if (!hotel) return;
    setSubmitting(true);

    try {
      // 1. Create the booking -- always starts as "Pending Payment",
      //    exactly as before payment integration existed.
      const booking = await createBooking({
        hotel_id: hotel.id,
        destination_id: destinationId ? Number(destinationId) : undefined,
        session_id: sessionId || undefined,
        ...form,
      });

      // 2. Kick off Razorpay checkout for that booking's amount.
      const scriptLoaded = await loadRazorpayScript();
      if (!scriptLoaded) {
        toast({
          title: "Payment unavailable",
          description: "Couldn't load the payment gateway. Your booking is saved as Pending Payment — you can retry from the confirmation page.",
        });
        navigate(`/booking-confirmation/${booking.booking_reference}`);
        return;
      }

      const order = await createPaymentOrder(booking.booking_reference);

      const razorpay = new (window as any).Razorpay({
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        order_id: order.order_id,
        name: "TravelMate",
        description: `Booking ${booking.booking_reference} — ${hotel.name}`,
        prefill: {
          name: form.guest_name,
          email: form.guest_email,
          contact: form.guest_phone,
        },
        theme: { color: "#0ea5e9" },
        handler: async (response: any) => {
          // Payment succeeded at the gateway -- verify signature server-side
          // before treating the booking as Confirmed.
          try {
            await verifyPayment(booking.booking_reference, {
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            });
            toast({ title: "Payment successful", description: "Your booking is confirmed!" });
          } catch {
            // Signature verification failed -- booking stays Pending Payment
            // on the backend; just inform the user here.
            toast({
              title: "Payment could not be verified",
              description: "Your booking is saved as Pending Payment.",
              variant: "destructive",
            });
          }
          navigate(`/booking-confirmation/${booking.booking_reference}`);
        },
        modal: {
          // User closed the checkout without paying -- booking remains
          // Pending Payment on the backend (nothing to undo).
          ondismiss: () => {
            toast({
              title: "Payment not completed",
              description: "Your booking is saved as Pending Payment. You can pay anytime from the confirmation page.",
            });
            navigate(`/booking-confirmation/${booking.booking_reference}`);
          },
        },
      });

      razorpay.on("payment.failed", () => {
        // Gateway-reported failure -- booking remains Pending Payment.
        toast({
          title: "Payment failed",
          description: "Your booking is saved as Pending Payment. You can retry payment anytime.",
          variant: "destructive",
        });
        navigate(`/booking-confirmation/${booking.booking_reference}`);
      });

      razorpay.open();
    } catch (e: any) {
      toast({
        title: "Booking failed",
        description: e.message || "Please check your details and try again.",
        variant: "destructive",
      });
      setSubmitting(false);
    }
  };

  if (loadingHotel) {
    return <PageLoader label="Loading hotel..." />;
  }

  if (!hotel) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">Hotel not found.</p>
        <Button variant="outline" onClick={() => navigate("/")}>
          <ArrowLeft className="h-4 w-4 mr-2" /> Back home
        </Button>
      </div>
    );
  }

  return (
    <div className="min-h-screen container mx-auto px-6 max-w-2xl py-16">
      <Button variant="ghost" size="sm" onClick={handleBack} className="mb-4">
        <ArrowLeft className="h-4 w-4 mr-1" /> Back
      </Button>

      {/* Step progress */}
      <div className="flex items-center gap-2 mb-6">
        {STEPS.map((label, i) => (
          <div key={label} className="flex items-center gap-2 flex-1">
            <div
              className={`h-8 w-8 rounded-full flex items-center justify-center text-xs font-semibold shrink-0 transition-colors ${
                i <= step ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
              }`}
            >
              {i + 1}
            </div>
            <span className={`text-xs ${i === step ? "font-medium" : "text-muted-foreground"} hidden sm:inline`}>
              {label}
            </span>
            {i < STEPS.length - 1 && <div className="flex-1 h-px bg-border" />}
          </div>
        ))}
      </div>

      <Card className="p-6 bg-card/95 backdrop-blur-md border border-white/20 animate-fade-up">
        <div className="flex items-center gap-2 mb-5">
          <BedDouble className="h-5 w-5 text-coral" />
          <h1 className="text-xl font-semibold">Book {hotel.name}</h1>
        </div>

        {/* Step 1: Guest details */}
        {step === 0 && (
          <div className="space-y-4">
            <div>
              <Label htmlFor="guest_name">Full name</Label>
              <Input
                id="guest_name"
                value={form.guest_name}
                onChange={(e) => update("guest_name", e.target.value)}
                placeholder="Your full name"
              />
            </div>
            <div>
              <Label htmlFor="guest_email">Email</Label>
              <Input
                id="guest_email"
                type="email"
                value={form.guest_email}
                onChange={(e) => update("guest_email", e.target.value)}
                placeholder="you@example.com"
              />
            </div>
            <div>
              <Label htmlFor="guest_phone">Phone number</Label>
              <Input
                id="guest_phone"
                value={form.guest_phone}
                onChange={(e) => update("guest_phone", e.target.value)}
                placeholder="+91 98765 43210"
              />
            </div>
            <Button
              variant="hero"
              className="w-full h-11 mt-2"
              disabled={!isStep1Valid}
              onClick={handleNext}
            >
              Continue <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          </div>
        )}

        {/* Step 2: Stay details */}
        {step === 1 && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="check_in">Check-in</Label>
                <Input
                  id="check_in"
                  type="date"
                  value={form.check_in_date}
                  onChange={(e) => update("check_in_date", e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="check_out">Check-out</Label>
                <Input
                  id="check_out"
                  type="date"
                  value={form.check_out_date}
                  onChange={(e) => update("check_out_date", e.target.value)}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="num_rooms">Rooms</Label>
                <Input
                  id="num_rooms"
                  type="number"
                  min={1}
                  value={form.num_rooms}
                  onChange={(e) => update("num_rooms", Number(e.target.value))}
                />
              </div>
              <div>
                <Label htmlFor="num_guests">Guests</Label>
                <Input
                  id="num_guests"
                  type="number"
                  min={1}
                  value={form.num_guests}
                  onChange={(e) => update("num_guests", Number(e.target.value))}
                />
              </div>
            </div>
            <div>
              <Label htmlFor="special_requests">Special requests (optional)</Label>
              <Textarea
                id="special_requests"
                value={form.special_requests}
                onChange={(e) => update("special_requests", e.target.value)}
                placeholder="Late check-in, extra bed, dietary needs..."
                rows={3}
              />
            </div>
            {nights > 0 && (
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <CalendarDays className="h-3 w-3" /> {nights} night{nights > 1 ? "s" : ""}
              </p>
            )}
            <Button
              variant="hero"
              className="w-full h-11 mt-2"
              disabled={!isStep2Valid}
              onClick={handleNext}
            >
              Review Booking <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          </div>
        )}

        {/* Step 3: Summary & confirm */}
        {step === 2 && (
          <div className="space-y-4">
            <div className="bg-muted/40 rounded-xl p-4 border border-white/10 space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground flex items-center gap-1">
                  <Users className="h-3 w-3" /> Guest
                </span>
                <span>{form.guest_name}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Contact</span>
                <span>{form.guest_email} · {form.guest_phone}</span>
              </div>
              <Separator />
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground flex items-center gap-1">
                  <CalendarDays className="h-3 w-3" /> Dates
                </span>
                <span>{form.check_in_date} → {form.check_out_date} ({nights} nights)</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Rooms / Guests</span>
                <span>{form.num_rooms} room(s) · {form.num_guests} guest(s)</span>
              </div>
              {form.special_requests && (
                <div className="flex justify-between text-sm gap-4">
                  <span className="text-muted-foreground flex items-center gap-1 shrink-0">
                    <MessageSquare className="h-3 w-3" /> Requests
                  </span>
                  <span className="text-right">{form.special_requests}</span>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between bg-primary/10 rounded-xl p-4">
              <span className="text-sm font-medium">Estimated total</span>
              <span className="text-lg font-bold">
                {estimatedTotal !== null ? `₹${estimatedTotal.toLocaleString()}` : "—"}
              </span>
            </div>

            <Badge variant="outline" className="w-fit">Status after booking: Pending Payment</Badge>
            <p className="text-xs text-muted-foreground">
              Payment isn't collected yet — this reserves your booking as "Pending Payment"
              until payment integration is available.
            </p>

            <Button
              variant="hero"
              className="w-full h-11"
              disabled={submitting}
              onClick={handleConfirm}
            >
              {submitting ? "Confirming..." : "Confirm Booking"}
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
};

export default BookingFlow;
