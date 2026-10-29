import { useState, useEffect } from "react";
import { HeroSection } from "../components/HeroSection";
import { RecommendationsSection } from "../components/RecommendationsSection";
import { Navigation } from "../components/Navigation";
import { LandmarkDetector } from "@/components/LandmarkDetector";
import { OCRTranslateBox } from "@/components/OCRTranslateBox";

const Index = () => {
  const [aiOutput, setAiOutput] = useState("");

  useEffect(() => {
    const handler = (event: any) => {
      setAiOutput(event.detail);
    };

    window.addEventListener("ai-recommendations", handler);

    return () => {
      window.removeEventListener("ai-recommendations", handler);
    };
  }, []);


  return (
    <div className="min-h-screen">
      <Navigation />
      <main>
        <HeroSection />
        <div className="container mx-auto px-6 max-w-4xl -mt-4 space-y-6">
          <LandmarkDetector />
          <OCRTranslateBox />
        </div>
        <RecommendationsSection aiOutput={aiOutput} />
      </main>
    </div>
  );
};

export default Index;
