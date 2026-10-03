import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { CheckCircle2, Home, Clock, CreditCard } from "lucide-react";
import { PageLoader } from "@/components/PageLoader";
import { getBooking, createPaymentOrder, verifyPayment } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

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

const BookingConfirmation = () => {
  const { reference } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [booking, setBooking] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [payingNow, setPayingNow] = useState(false);

  const refresh = () => {
    if (!reference) return Promise.resolve();
    return getBooking(reference).then(setBooking).catch(() => setBooking(null));
  };

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, [reference]);

  const handlePayNow = async () => {
    if (!booking) return;
    setPayingNow(true);

    try {
      const scriptLoaded = await loadRazorpayScript();
      if (!scriptLoaded) {
        toast({
          title: "Payment unavailable",
          description: "Couldn't load the payment gateway. Please try again shortly.",
          variant: "destructive",
        });
        setPayingNow(false);
        return;
      }

      const order = await createPaymentOrder(booking.booking_reference);

      const razorpay = new (window as any).Razorpay({
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        order_id: order.order_id,
        name: "TravelMate",
        description: `Booking ${booking.booking_reference}`,
        prefill: {
          name: booking.guest_name,
          email: booking.guest_email,
          contact: booking.guest_phone,
        },
        theme: { color: "#0ea5e9" },
        handler: async (response: any) => {
          try {
            await verifyPayment(booking.booking_reference, {
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            });
            toast({ title: "Payment successful", description: "Your booking is confirmed!" });
          } catch {
            toast({
              title: "Payment could not be verified",
              description: "Your booking is still saved as Pending Payment.",
              variant: "destructive",
            });
          }
          await refresh();
          setPayingNow(false);
        },
        modal: {
          ondismiss: () => setPayingNow(false),
        },
      });

      razorpay.on("payment.failed", () => {
        toast({
          title: "Payment failed",
          description: "Your booking is still saved as Pending Payment. You can retry anytime.",
          variant: "destructive",
        });
        setPayingNow(false);
      });

      razorpay.open();
    } catch (e: any) {
      toast({ title: "Couldn't start payment", description: e.message, variant: "destructive" });
      setPayingNow(false);
    }
  };

  if (loading) {
    return <PageLoader label="Loading booking..." />;
  }

  if (!booking) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">We couldn't find that booking.</p>
        <Button variant="outline" onClick={() => navigate("/")}>
          <Home className="h-4 w-4 mr-2" /> Back home
        </Button>
      </div>
    );
  }

  const isConfirmed = booking.status === "Confirmed";
  const isPending = booking.status === "Pending Payment";

  return (
    <div className="min-h-screen flex items-center justify-center px-6 py-16">
      <Card className="w-full max-w-lg p-8 bg-card/95 backdrop-blur-md border border-white/20 animate-fade-up text-center">
        <div
          className={`mx-auto h-16 w-16 rounded-full flex items-center justify-center mb-4 ${
            isConfirmed ? "bg-green-500/15" : "bg-amber-500/15"
          }`}
        >
          {isConfirmed ? (
            <CheckCircle2 className="h-9 w-9 text-green-600" />
          ) : (
            <Clock className="h-9 w-9 text-amber-500" />
          )}
        </div>
        <h1 className="text-2xl font-bold mb-1">
          {isConfirmed ? "Payment Successful!" : "Booking Received"}
        </h1>
        <p className="text-sm text-muted-foreground mb-4">
          {isConfirmed
            ? `Your stay at ${booking.hotel_name} is confirmed.`
            : `Your stay at ${booking.hotel_name} is reserved, pending payment.`}
        </p>

        <div className="bg-muted/40 rounded-xl p-4 mb-4">
          <p className="text-xs text-muted-foreground mb-1">Booking Reference</p>
          <p className="text-2xl font-mono font-bold tracking-wider">{booking.booking_reference}</p>
        </div>

        <Badge
          variant="outline"
          className={`mb-4 flex items-center gap-1 w-fit mx-auto ${
            isConfirmed ? "border-green-500 text-green-700 dark:text-green-400" : ""
          }`}
        >
          {isConfirmed ? <CheckCircle2 className="h-3 w-3" /> : <Clock className="h-3 w-3" />}
          {booking.status}
        </Badge>

        <div className="text-left space-y-2 text-sm mb-4">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Guest</span>
            <span>{booking.guest_name}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Dates</span>
            <span>{booking.check_in_date} → {booking.check_out_date}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Rooms / Guests</span>
            <span>{booking.num_rooms} room(s) · {booking.num_guests} guest(s)</span>
          </div>
          {isConfirmed && booking.payment_reference && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Payment Reference</span>
              <span className="font-mono text-xs">{booking.payment_reference}</span>
            </div>
          )}
          <Separator />
          <div className="flex justify-between font-medium">
            <span>{isConfirmed ? "Amount paid" : "Estimated total"}</span>
            <span>
              {booking.total_amount ? `₹${Number(booking.total_amount).toLocaleString()}` : "—"}
            </span>
          </div>
        </div>

        {isPending && (
          <>
            <p className="text-xs text-muted-foreground mb-4">
              Your booking is held as "Pending Payment" until payment is completed.
            </p>
            <Button
              variant="hero"
              className="w-full h-11 mb-3"
              onClick={handlePayNow}
              disabled={payingNow}
            >
              <CreditCard className="h-4 w-4 mr-2" />
              {payingNow ? "Opening payment..." : "Complete Payment"}
            </Button>
          </>
        )}

        <Button variant="outline" className="w-full h-11" onClick={() => navigate("/")}>
          <Home className="h-4 w-4 mr-2" /> Back to TravelMate
        </Button>
      </Card>
    </div>
  );
};

export default BookingConfirmation;
