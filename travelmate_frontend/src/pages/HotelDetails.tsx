import { useEffect, useState } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  Star,
  MapPin,
  Wallet,
  Users,
  BedDouble,
  CheckCircle2,
  ArrowLeft,
} from "lucide-react";
import { PageLoader } from "@/components/PageLoader";
import { getHotelDetails, selectHotel } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

const PLACEHOLDER_PHOTO =
  "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=1200&q=80";

const DestinationHotelPage = () => {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { toast } = useToast();

  const sessionId = searchParams.get("session_id");
  const destinationId = searchParams.get("destination_id");

  const [hotel, setHotel] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState(false);

  useEffect(() => {
    if (!id) return;
    getHotelDetails(id)
      .then(setHotel)
      .catch(() => setHotel(null))
      .finally(() => setLoading(false));
  }, [id]);

  const handleSelect = async () => {
    if (!sessionId || !destinationId || !hotel) {
      toast({
        title: "Can't select this hotel",
        description: "Missing trip context — please select a hotel from your AI-generated plan.",
        variant: "destructive",
      });
      return;
    }

    setSelecting(true);
    try {
      await selectHotel(sessionId, Number(destinationId), hotel.id);
      setSelected(true);
      toast({ title: "Hotel selected", description: `${hotel.name} added to your trip plan.` });
      setTimeout(() => navigate("/"), 1200);
    } catch {
      toast({
        title: "Something went wrong",
        description: "Could not update your plan. Please try again.",
        variant: "destructive",
      });
    }
    setSelecting(false);
  };

  if (loading) {
    return <PageLoader label="Loading details..." />;
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

  const photos: string[] =
    hotel.photos && hotel.photos.length > 0 ? hotel.photos : [PLACEHOLDER_PHOTO];

  return (
    <div className="min-h-screen bg-background">
      {/* Photo header */}
      <div className="relative h-72 sm:h-96 w-full overflow-hidden">
        <img src={photos[0]} className="w-full h-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-t from-background via-background/20 to-transparent" />
        <Button
          variant="secondary"
          size="sm"
          className="absolute top-4 left-4"
          onClick={() => navigate(-1)}
        >
          <ArrowLeft className="h-4 w-4 mr-1" /> Back
        </Button>
      </div>

      <div className="container mx-auto px-6 max-w-4xl -mt-16 relative z-10 pb-16">
        <Card className="p-6 bg-card/95 backdrop-blur-md border border-white/20 shadow-xl">
          <div className="flex items-start justify-between flex-wrap gap-2">
            <div>
              <h1 className="text-3xl font-bold">{hotel.name}</h1>
              <p className="flex items-center gap-1 text-muted-foreground text-sm mt-1">
                <MapPin className="h-4 w-4" />
                {hotel.location?.destination_name}
                {hotel.location?.country ? `, ${hotel.location.country}` : ""}
              </p>
            </div>
            {hotel.star_rating && (
              <span className="flex items-center gap-1 text-lg font-semibold">
                <Star className="h-5 w-5 fill-yellow-400 text-yellow-400" />
                {hotel.star_rating}
              </span>
            )}
          </div>

          <div className="flex flex-wrap gap-2 mt-4">
            {hotel.accommodation_type && (
              <Badge className="capitalize">{hotel.accommodation_type}</Badge>
            )}
            <Badge variant="outline" className="capitalize">{hotel.price_tier} tier</Badge>
            {hotel.price_per_night && (
              <Badge variant="outline">₹{hotel.price_per_night}/night</Badge>
            )}
          </div>

          <Separator className="my-5" />

          {/* Description */}
          {hotel.description && (
            <div className="mb-6">
              <h2 className="text-lg font-semibold mb-2">About this stay</h2>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {hotel.description}
              </p>
            </div>
          )}

          {/* Amenities */}
          {hotel.amenities?.length > 0 && (
            <div className="mb-6">
              <h2 className="text-lg font-semibold mb-2">Amenities</h2>
              <div className="flex flex-wrap gap-2">
                {hotel.amenities.map((a: string) => (
                  <Badge key={a} variant="outline" className="font-normal capitalize">
                    {a.trim()}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Room types (mock) */}
          {hotel.room_types?.length > 0 && (
            <div className="mb-6">
              <h2 className="text-lg font-semibold mb-2 flex items-center gap-2">
                <BedDouble className="h-5 w-5 text-coral" /> Available Room Types
              </h2>
              <p className="text-xs text-muted-foreground mb-3">
                Sample rates — booking isn't available yet.
              </p>
              <div className="grid sm:grid-cols-3 gap-3">
                {hotel.room_types.map((room: any) => (
                  <div
                    key={room.type}
                    className="bg-muted/40 rounded-xl p-3 border border-white/10"
                  >
                    <p className="font-medium text-sm mb-1">{room.type}</p>
                    <p className="text-xs text-muted-foreground flex items-center gap-1 mb-1">
                      <Users className="h-3 w-3" /> Up to {room.capacity} guests · {room.bed}
                    </p>
                    <p className="text-sm font-semibold flex items-center gap-1">
                      <Wallet className="h-3 w-3" /> ₹{room.price_per_night}/night
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Nearby attractions */}
          {hotel.nearby_attractions?.length > 0 && (
            <div className="mb-6">
              <h2 className="text-lg font-semibold mb-2">Nearby Attractions</h2>
              <div className="flex flex-wrap gap-2">
                {hotel.nearby_attractions.map((a: any, i: number) => (
                  <Badge key={i} variant="outline" className="font-normal">
                    {a.name}
                    {a.distance_m ? ` · ${Math.round(a.distance_m)}m` : ""}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          <Separator className="my-5" />

          <div className="grid sm:grid-cols-2 gap-3">
            <Button
              variant="hero"
              size="lg"
              className="h-12"
              onClick={handleSelect}
              disabled={selecting || selected}
            >
              {selected ? (
                <>
                  <CheckCircle2 className="h-5 w-5 mr-2" /> Selected for your trip
                </>
              ) : selecting ? (
                "Updating your plan..."
              ) : (
                "Select this Hotel"
              )}
            </Button>
            <Button
              variant="outline"
              size="lg"
              className="h-12"
              onClick={() => {
                const params = new URLSearchParams();
                if (sessionId) params.set("session_id", sessionId);
                if (destinationId) params.set("destination_id", destinationId);
                navigate(`/booking/${hotel.id}?${params.toString()}`);
              }}
            >
              Book Now
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default DestinationHotelPage;
