import { useEffect, useState } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  Star,
  Briefcase,
  Users,
  CalendarDays,
  CheckCircle2,
  ArrowLeft,
  Building2,
} from "lucide-react";
import { PageLoader } from "@/components/PageLoader";
import { getPackageDetails, selectPackage } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

const PLACEHOLDER_PHOTO =
  "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?w=1200&q=80";

const PackageDetails = () => {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { toast } = useToast();

  const sessionId = searchParams.get("session_id");
  const destinationId = searchParams.get("destination_id");

  const [pkg, setPkg] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState(false);

  useEffect(() => {
    if (!id) return;
    getPackageDetails(id)
      .then(setPkg)
      .catch(() => setPkg(null))
      .finally(() => setLoading(false));
  }, [id]);

  const handleSelect = async () => {
    if (!sessionId || !destinationId || !pkg) {
      toast({
        title: "Can't select this package",
        description: "Missing trip context — please select a package from your AI-generated plan.",
        variant: "destructive",
      });
      return;
    }

    setSelecting(true);
    try {
      await selectPackage(sessionId, Number(destinationId), pkg.id);
      setSelected(true);
      toast({ title: "Package selected", description: `${pkg.title} added to your trip plan.` });
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

  if (!pkg) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">Package not found.</p>
        <Button variant="outline" onClick={() => navigate("/")}>
          <ArrowLeft className="h-4 w-4 mr-2" /> Back home
        </Button>
      </div>
    );
  }

  const photos: string[] = pkg.photos && pkg.photos.length > 0 ? pkg.photos : [PLACEHOLDER_PHOTO];

  return (
    <div className="min-h-screen bg-background">
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
              <h1 className="text-3xl font-bold">{pkg.title}</h1>
              {pkg.partner_name && (
                <p className="flex items-center gap-1 text-muted-foreground text-sm mt-1">
                  <Building2 className="h-4 w-4" /> by {pkg.partner_name}
                </p>
              )}
            </div>
            {pkg.rating && (
              <span className="flex items-center gap-1 text-lg font-semibold">
                <Star className="h-5 w-5 fill-yellow-400 text-yellow-400" />
                {pkg.rating}
              </span>
            )}
          </div>

          <div className="flex flex-wrap gap-2 mt-4">
            {pkg.category && <Badge className="capitalize">{pkg.category.replace("_", " ")}</Badge>}
            <Badge variant="outline" className="capitalize">{pkg.price_tier} tier</Badge>
            {pkg.price_per_package && <Badge variant="outline">₹{pkg.price_per_package}/package</Badge>}
            {pkg.duration_days && (
              <Badge variant="outline" className="flex items-center gap-1">
                <CalendarDays className="h-3 w-3" /> {pkg.duration_days} days
              </Badge>
            )}
            {pkg.capacity && (
              <Badge variant="outline" className="flex items-center gap-1">
                <Users className="h-3 w-3" /> Up to {pkg.capacity} travelers
              </Badge>
            )}
          </div>

          <Separator className="my-5" />

          {pkg.description && (
            <div className="mb-6">
              <h2 className="text-lg font-semibold mb-2">About this package</h2>
              <p className="text-sm text-muted-foreground leading-relaxed">{pkg.description}</p>
            </div>
          )}

          {pkg.amenities?.length > 0 && (
            <div className="mb-6">
              <h2 className="text-lg font-semibold mb-2 flex items-center gap-2">
                <Briefcase className="h-5 w-5 text-coral" /> Included Services
              </h2>
              <div className="flex flex-wrap gap-2">
                {pkg.amenities.map((a: string) => (
                  <Badge key={a} variant="outline" className="font-normal capitalize">
                    {a.trim()}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          <Separator className="my-5" />

          <Button
            variant="hero"
            size="lg"
            className="w-full h-12"
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
              "Select this Package"
            )}
          </Button>
          <p className="text-xs text-muted-foreground text-center mt-2">
            Booking isn't available for packages yet — selecting updates your trip plan and budget.
          </p>
        </Card>
      </div>
    </div>
  );
};

export default PackageDetails;
