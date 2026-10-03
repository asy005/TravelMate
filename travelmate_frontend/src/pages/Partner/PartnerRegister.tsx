import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Building2 } from "lucide-react";
import { registerPartner } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

const PARTNER_TYPES = [
  { value: "hotel", label: "Hotel" },
  { value: "homestay", label: "Homestay" },
  { value: "resort", label: "Resort" },
  { value: "travel_agency", label: "Travel Agency" },
  { value: "tour_operator", label: "Tour Operator" },
  { value: "local_guide", label: "Local Guide" },
];

const PartnerRegister = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    business_name: "",
    partner_type: "",
    contact_email: "",
    contact_phone: "",
    description: "",
  });

  const update = (field: string, value: string) => setForm((f) => ({ ...f, [field]: value }));

  const handleSubmit = async () => {
    if (!form.business_name.trim() || !form.partner_type) {
      toast({ title: "Missing details", description: "Business name and partner type are required.", variant: "destructive" });
      return;
    }
    setSubmitting(true);
    try {
      await registerPartner(form);
      toast({ title: "Welcome to the TravelMate Partner Portal!" });
      navigate("/partner/dashboard");
    } catch (e: any) {
      toast({ title: "Registration failed", description: e.message, variant: "destructive" });
    }
    setSubmitting(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-6 py-24">
      <Card className="w-full max-w-lg p-8 bg-card/95 backdrop-blur-md border border-white/20 animate-fade-up">
        <div className="flex items-center gap-2 mb-1">
          <Building2 className="h-6 w-6 text-primary" />
          <h1 className="text-2xl font-bold">Become a TravelMate Partner</h1>
        </div>
        <p className="text-sm text-muted-foreground mb-6">
          List your hotel, homestay, resort, or tour packages on TravelMate.
        </p>

        <div className="space-y-4">
          <div>
            <Label htmlFor="business_name">Business name</Label>
            <Input
              id="business_name"
              value={form.business_name}
              onChange={(e) => update("business_name", e.target.value)}
              placeholder="e.g. Blue Mountain Resorts"
            />
          </div>

          <div>
            <Label>Partner type</Label>
            <Select value={form.partner_type} onValueChange={(v) => update("partner_type", v)}>
              <SelectTrigger>
                <SelectValue placeholder="Select a partner type" />
              </SelectTrigger>
              <SelectContent>
                {PARTNER_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label htmlFor="contact_email">Contact email</Label>
            <Input
              id="contact_email"
              type="email"
              value={form.contact_email}
              onChange={(e) => update("contact_email", e.target.value)}
              placeholder="business@example.com"
            />
          </div>

          <div>
            <Label htmlFor="contact_phone">Contact phone</Label>
            <Input
              id="contact_phone"
              value={form.contact_phone}
              onChange={(e) => update("contact_phone", e.target.value)}
              placeholder="+91 98765 43210"
            />
          </div>

          <div>
            <Label htmlFor="description">About your business</Label>
            <Textarea
              id="description"
              value={form.description}
              onChange={(e) => update("description", e.target.value)}
              rows={3}
              placeholder="Tell travelers what makes your business special..."
            />
          </div>

          <Button variant="hero" className="w-full h-11" onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Registering..." : "Register as a Partner"}
          </Button>
        </div>
      </Card>
    </div>
  );
};

export default PartnerRegister;
