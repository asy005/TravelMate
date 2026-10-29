import { useState, useRef, useContext, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Building2, Upload, X, AlertCircle } from "lucide-react";
import { registerPartner, uploadPartnerPhoto, getMyPartnerProfile } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { AuthContext } from "@/hooks/AuthContext";

const PARTNER_TYPES = [
  { value: "hotel", label: "Hotel" },
  { value: "homestay", label: "Homestay" },
  { value: "resort", label: "Resort" },
  { value: "travel_agency", label: "Travel Agency" },
  { value: "tour_operator", label: "Tour Operator" },
  { value: "local_guide", label: "Local Guide" },
];

const MAX_FILE_MB = 5;
const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"];

interface PhotoPreview {
  file: File;
  previewUrl: string;
  uploadedUrl?: string;
  error?: string;
}

const PartnerRegister = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { token: contextToken } = useContext(AuthContext);
  const token = contextToken || localStorage.getItem("travelmate_token");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [submitting, setSubmitting] = useState(false);
  const [photos, setPhotos] = useState<PhotoPreview[]>([]);
  const [uploadingPhotos, setUploadingPhotos] = useState(false);

  const [form, setForm] = useState({
    business_name: "",
    partner_type: "",
    contact_email: "",
    contact_phone: "",
    description: "",
    address: "",
    city: "",
    state: "",
    postal_code: "",
  });

  // Check if current authenticated user already has a partner profile
  useEffect(() => {
    if (!token) return;
    getMyPartnerProfile()
      .then((profile) => {
        if (profile) {
          toast({
            title: "Already registered",
            description: "You already have a registered partner profile. Taking you to your dashboard...",
          });
          navigate("/partner/dashboard", { replace: true });
        }
      })
      .catch(() => {});
  }, [token, navigate, toast]);

  const update = (field: string, value: string) =>
    setForm((f) => ({ ...f, [field]: value }));

  // ── Photo handling ────────────────────────────────────────────────────────
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const newPreviews: PhotoPreview[] = files.map((file) => {
      if (!ALLOWED_TYPES.includes(file.type)) {
        return {
          file,
          previewUrl: "",
          error: `Unsupported type: ${file.type}. Use JPEG, PNG, WebP, or GIF.`,
        };
      }
      if (file.size > MAX_FILE_MB * 1024 * 1024) {
        return {
          file,
          previewUrl: "",
          error: `File too large (max ${MAX_FILE_MB} MB).`,
        };
      }
      return { file, previewUrl: URL.createObjectURL(file) };
    });
    setPhotos((prev) => [...prev, ...newPreviews]);
    // Reset file input so the same file can be re-added after removal
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const removePhoto = (index: number) => {
    setPhotos((prev) => {
      const copy = [...prev];
      const removed = copy.splice(index, 1)[0];
      if (removed.previewUrl) URL.revokeObjectURL(removed.previewUrl);
      return copy;
    });
  };

  // ── Submit ────────────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!token) {
      toast({
        title: "Sign in required",
        description: "Please sign in before registering as a partner.",
        variant: "destructive",
      });
      navigate("/partner/login?redirect=/partner/register");
      return;
    }

    if (!form.business_name.trim() || !form.partner_type) {
      toast({
        title: "Missing details",
        description: "Business name and partner type are required.",
        variant: "destructive",
      });
      return;
    }

    const invalidPhotos = photos.filter((p) => p.error);
    if (invalidPhotos.length > 0) {
      toast({
        title: "Remove invalid photos",
        description: "Please remove photos with errors before submitting.",
        variant: "destructive",
      });
      return;
    }

    setSubmitting(true);

    try {
      // 1. Upload un-uploaded valid photos
      const validPhotos = photos.filter((p) => !p.error && p.file);
      const uploadedUrls: string[] = [];

      if (validPhotos.length > 0) {
        setUploadingPhotos(true);
        for (let i = 0; i < validPhotos.length; i++) {
          const item = validPhotos[i];
          if (item.uploadedUrl) {
            uploadedUrls.push(item.uploadedUrl);
          } else {
            const res = await uploadPartnerPhoto(item.file);
            uploadedUrls.push(res.url);
            setPhotos((prev) =>
              prev.map((p) => (p.file === item.file ? { ...p, uploadedUrl: res.url } : p))
            );
          }
        }
        setUploadingPhotos(false);
      }

      // 2. Submit partner registration
      await registerPartner({
        business_name: form.business_name.trim(),
        partner_type: form.partner_type,
        contact_email: form.contact_email.trim() || undefined,
        contact_phone: form.contact_phone.trim() || undefined,
        description: form.description.trim() || undefined,
        address: form.address.trim() || undefined,
        city: form.city.trim() || undefined,
        state: form.state.trim() || undefined,
        postal_code: form.postal_code.trim() || undefined,
        photos: uploadedUrls,
      });

      localStorage.setItem("travelmate_role", "partner");
      toast({
        title: "Registration successful!",
        description: "Welcome to the TravelMate Partner Portal.",
      });
      navigate("/partner/dashboard");
    } catch (e: any) {
      const msg = e?.message || "Registration failed";
      if (msg.toLowerCase().includes("already registered")) {
        toast({
          title: "Already registered",
          description: "This account is already registered as a partner. Redirecting to your dashboard...",
        });
        navigate("/partner/dashboard");
      } else {
        toast({
          title: "Registration failed",
          description: msg,
          variant: "destructive",
        });
      }
    } finally {
      setSubmitting(false);
      setUploadingPhotos(false);
    }
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

        {/* ── Unauthenticated banner (shown only if not logged in, keeping page layout intact) ── */}
        {!token && (
          <div className="bg-destructive/10 border border-destructive/20 rounded-xl p-4 mb-6 flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-semibold text-destructive">Sign in required</p>
              <p className="text-muted-foreground text-xs mt-0.5">
                You need to be logged in to register as a partner. Please sign in or create an account.
              </p>
              <div className="flex gap-2 mt-3">
                <Button size="sm" variant="hero" asChild>
                  <Link to="/partner/login">Sign In</Link>
                </Button>
                <Button size="sm" variant="outline" asChild>
                  <Link to="/signup">Create Account</Link>
                </Button>
              </div>
            </div>
          </div>
        )}

        <div className="space-y-4">
          {/* ── Business info ── */}
          <div>
            <Label htmlFor="business_name">Business name *</Label>
            <Input
              id="business_name"
              value={form.business_name}
              onChange={(e) => update("business_name", e.target.value)}
              placeholder="e.g. Blue Mountain Resorts"
            />
          </div>

          <div>
            <Label>Partner type *</Label>
            <Select
              value={form.partner_type}
              onValueChange={(v) => update("partner_type", v)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a partner type" />
              </SelectTrigger>
              <SelectContent>
                {PARTNER_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
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

          {/* ── Location fields ── */}
          <div className="pt-2 border-t border-white/10">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
              Property Location
            </p>
            <div className="space-y-3">
              <div>
                <Label htmlFor="address">Street address</Label>
                <Input
                  id="address"
                  value={form.address}
                  onChange={(e) => update("address", e.target.value)}
                  placeholder="123 Beach Road"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="city">City</Label>
                  <Input
                    id="city"
                    value={form.city}
                    onChange={(e) => update("city", e.target.value)}
                    placeholder="Panaji"
                  />
                </div>
                <div>
                  <Label htmlFor="state">State</Label>
                  <Input
                    id="state"
                    value={form.state}
                    onChange={(e) => update("state", e.target.value)}
                    placeholder="Goa"
                  />
                </div>
              </div>
              <div className="w-1/2">
                <Label htmlFor="postal_code">Postal code</Label>
                <Input
                  id="postal_code"
                  value={form.postal_code}
                  onChange={(e) => update("postal_code", e.target.value)}
                  placeholder="403001"
                />
              </div>
            </div>
          </div>

          {/* ── Photo upload ── */}
          <div className="pt-2 border-t border-white/10">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
              Property Photos
            </p>
            <p className="text-xs text-muted-foreground mb-3">
              Accepted: JPEG, PNG, WebP, GIF · Max {MAX_FILE_MB} MB each
            </p>

            {photos.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-3">
                {photos.map((p, i) => (
                  <div key={i} className="relative group">
                    {p.error ? (
                      <div className="w-20 h-20 rounded-lg border border-destructive bg-destructive/10 flex flex-col items-center justify-center p-1">
                        <AlertCircle className="h-5 w-5 text-destructive mb-1" />
                        <span className="text-[10px] text-destructive text-center leading-tight">
                          {p.error}
                        </span>
                      </div>
                    ) : (
                      <img
                        src={p.previewUrl}
                        alt="Preview"
                        className="w-20 h-20 object-cover rounded-lg border border-white/20"
                      />
                    )}
                    {p.uploadedUrl && (
                      <Badge
                        className="absolute -top-1 -right-1 text-[9px] px-1 py-0 h-4"
                        variant="default"
                      >
                        ✓
                      </Badge>
                    )}
                    <button
                      type="button"
                      onClick={() => removePhoto(i)}
                      className="absolute -top-1 -left-1 bg-destructive text-white rounded-full w-5 h-5 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                      aria-label="Remove photo"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              multiple
              className="hidden"
              onChange={handleFileChange}
              aria-label="Upload property photos"
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              disabled={submitting}
              className="w-full"
            >
              <Upload className="h-4 w-4 mr-2" />
              {photos.length === 0 ? "Add Photos" : "Add More Photos"}
            </Button>
          </div>

          {/* ── Submit button ── */}
          <Button
            variant="hero"
            className="w-full h-11 mt-2"
            onClick={handleSubmit}
            disabled={submitting}
          >
            {uploadingPhotos
              ? "Uploading photos..."
              : submitting
              ? "Registering..."
              : "Register as a Partner"}
          </Button>
        </div>
      </Card>
    </div>
  );
};

export default PartnerRegister;
