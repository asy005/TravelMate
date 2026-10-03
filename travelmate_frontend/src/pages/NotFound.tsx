import { useLocation, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Compass, Home } from "lucide-react";

const NotFound = () => {
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    console.error("404 Error: User attempted to access non-existent route:", location.pathname);
  }, [location.pathname]);

  return (
    <div className="flex min-h-screen items-center justify-center px-6">
      <Card className="w-full max-w-md p-8 text-center bg-card/95 backdrop-blur-md border border-white/20 animate-fade-up">
        <div className="mx-auto h-14 w-14 rounded-full bg-coral/15 flex items-center justify-center mb-4">
          <Compass className="h-7 w-7 text-coral" aria-hidden="true" />
        </div>
        <h1 className="mb-2 text-4xl font-bold">404</h1>
        <p className="mb-6 text-muted-foreground">
          Looks like this page wandered off the map.
        </p>
        <Button variant="hero" className="w-full h-11" onClick={() => navigate("/")}>
          <Home className="h-4 w-4 mr-2" /> Back to TravelMate
        </Button>
      </Card>
    </div>
  );
};

export default NotFound;
