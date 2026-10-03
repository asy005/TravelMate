import { useContext, useEffect, useState } from "react";
import { AuthContext } from "@/hooks/AuthContext";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import { Heart, MapPin } from "lucide-react";

const Favorites = () => {
  const { token } = useContext(AuthContext);
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      window.location.href = "/login";
      return;
    }

    fetch("http://127.0.0.1:8000/favorites", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => res.json())
      .then((data) => setItems(Array.isArray(data) ? data : []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <div className="container mx-auto px-6 max-w-4xl pt-28 pb-16">
      <div className="flex items-center gap-2 mb-6">
        <Heart className="h-6 w-6 text-coral" aria-hidden="true" />
        <h1 className="text-3xl font-bold">Your Favorites</h1>
      </div>

      {loading ? (
        <div className="grid sm:grid-cols-2 gap-4" aria-busy="true" aria-label="Loading favorites">
          {[...Array(4)].map((_, i) => (
            <Card key={i} className="p-4 border border-white/10">
              <Skeleton className="h-5 w-2/3 mb-2" />
              <Skeleton className="h-4 w-1/3" />
            </Card>
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={Heart}
          title="No favorites yet"
          description="Save destinations you love while chatting with the AI assistant, and they'll show up here."
          actionLabel="Start planning a trip"
          onAction={() => (window.location.href = "/")}
        />
      ) : (
        <div className="grid sm:grid-cols-2 gap-4">
          {items.map((i: any) => (
            <Card
              key={i.id}
              className="p-4 bg-card/95 backdrop-blur-md border border-white/20 flex items-center gap-3 animate-fade-up"
            >
              <div className="h-10 w-10 rounded-full bg-coral/15 flex items-center justify-center shrink-0">
                <MapPin className="h-5 w-5 text-coral" aria-hidden="true" />
              </div>
              <div>
                <p className="font-semibold">{i.name}</p>
                {i.country && <p className="text-xs text-muted-foreground">{i.country}</p>}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default Favorites;
