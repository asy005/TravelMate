import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";

import Index from "./pages/Index";
import NotFound from "./pages/NotFound";
import DestinationPage from "./pages/DestinationPage";
import Login from "./pages/Auth/Login";
import Signup from "./pages/Auth/Signup";
import ForgotPassword from "./pages/Auth/ForgotPassword";
import ResetPassword from "./pages/Auth/ResetPassword";
import Favorites from "./pages/Favorites";
import Chatbot from "./pages/Chatbot";
import HotelDetails from "./pages/HotelDetails";
import PackageDetails from "./pages/PackageDetails";
import BookingFlow from "./pages/BookingFlow";
import BookingConfirmation from "./pages/BookingConfirmation";
import PartnerRegister from "./pages/Partner/PartnerRegister";
import PartnerDashboard from "./pages/Partner/PartnerDashboard";
import { PageTransition } from "@/components/PageTransition";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<PageTransition><Index /></PageTransition>} />

          {/* Destination Details Page */}
          <Route path="/destination/:id" element={<PageTransition><DestinationPage /></PageTransition>} />

          {/* Auth */}
          <Route path="/login" element={<PageTransition><Login /></PageTransition>} />
          <Route path="/signup" element={<PageTransition><Signup /></PageTransition>} />
          <Route path="/forgot-password" element={<PageTransition><ForgotPassword /></PageTransition>} />
          <Route path="/reset-password" element={<PageTransition><ResetPassword /></PageTransition>} />

          {/* Hotel Details */}
          <Route path="/hotel/:id" element={<PageTransition><HotelDetails /></PageTransition>} />
          <Route path="/package/:id" element={<PageTransition><PackageDetails /></PageTransition>} />

          {/* Hotel Booking */}
          <Route path="/booking/:hotelId" element={<PageTransition><BookingFlow /></PageTransition>} />
          <Route path="/booking-confirmation/:reference" element={<PageTransition><BookingConfirmation /></PageTransition>} />

          {/* Partner Portal */}
          <Route path="/partner/register" element={<PageTransition><PartnerRegister /></PageTransition>} />
          <Route path="/partner/dashboard" element={<PageTransition><PartnerDashboard /></PageTransition>} />

          {/* Favorites */}
          <Route path="/favorites" element={<PageTransition><Favorites /></PageTransition>} />

          {/* AI Chat */}
          <Route path="/chat" element={<PageTransition><Chatbot /></PageTransition>} />

          {/* Catch all */}
          <Route path="*" element={<PageTransition><NotFound /></PageTransition>} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
