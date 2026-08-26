import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, Eye, EyeOff, Globe } from "lucide-react";
import { Button, Input } from "../components/ui";
import SEO from "../components/SEO";
import { useAuth } from "../context/AuthContext";

function AuthShell({ children, title, subtitle }: {
  children: React.ReactNode;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="min-h-full bg-slate-50 flex flex-col">
      <SEO title={title} description={subtitle || title} noIndex path="/login" />
      <header className="p-6 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <div className="w-8 h-8 bg-indigo-600 rounded-xl flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="6" stroke="white" strokeWidth="1.5" opacity="0.5" />
              <circle cx="8" cy="8" r="3" fill="white" />
            </svg>
          </div>
          <span className="font-bold text-slate-900">Presence</span>
        </Link>
        <div className="flex items-center gap-2 px-3 py-1.5 border border-slate-200 rounded-lg bg-white text-sm text-slate-600 cursor-pointer hover:bg-slate-50">
          <Globe size={14} /> EN
        </div>
      </header>
      <div className="flex-1 flex items-center justify-center px-4 py-8">
        <div className="w-full max-w-sm">
          <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm">
            <div className="mb-6">
              <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
              {subtitle && <p className="text-sm text-slate-500 mt-1">{subtitle}</p>}
            </div>
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}

export function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);
    try {
      await login(email, password);
      navigate("/app/dashboard");
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ||
        err?.response?.data?.non_field_errors?.[0] ||
        "Invalid email or password.";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthShell title="Welcome back" subtitle="Sign in to your Presence account">
      <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
        {error && (
          <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
            {error}
          </div>
        )}
        <Input
          label="Email address"
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={setEmail}
        />
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-slate-700">Password</label>
          <div className="relative">
            <input
              type={showPass ? "text" : "password"}
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 pr-10 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            />
            <button
              type="button"
              onClick={() => setShowPass(!showPass)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              {showPass ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          </div>
          <div className="text-right">
            <Link to="/forgot-password" className="text-xs text-indigo-600 hover:text-indigo-700">
              Forgot password?
            </Link>
          </div>
        </div>
        <Button type="submit" className="w-full mt-2" disabled={isLoading}>
          {isLoading ? "Signing in..." : "Sign in"}
        </Button>
        <div className="relative flex items-center gap-3 my-2">
          <div className="flex-1 h-px bg-slate-200" />
          <span className="text-xs text-slate-400">or</span>
          <div className="flex-1 h-px bg-slate-200" />
        </div>
        <button
          type="button"
          disabled
          className="w-full flex items-center justify-center gap-3 border border-slate-300 rounded-lg py-2.5 text-sm font-medium text-slate-700 opacity-50 cursor-not-allowed"
        >
          <svg width="16" height="16" viewBox="0 0 18 18">
            <path fill="#4285F4" d="M16.51 8H8.98v3h4.3c-.18 1-.74 1.48-1.6 2.04v2.01h2.6a7.8 7.8 0 0 0 2.38-5.88c0-.57-.05-.66-.15-1.18z" />
            <path fill="#34A853" d="M8.98 17c2.16 0 3.97-.72 5.3-1.94l-2.6-2a4.8 4.8 0 0 1-7.18-2.54H1.83v2.07A8 8 0 0 0 8.98 17z" />
            <path fill="#FBBC05" d="M4.5 10.52a4.8 4.8 0 0 1 0-3.04V5.41H1.83a8 8 0 0 0 0 7.18l2.67-2.07z" />
            <path fill="#EA4335" d="M8.98 4.18c1.17 0 2.23.4 3.06 1.2l2.3-2.3A8 8 0 0 0 1.83 5.4L4.5 7.49a4.77 4.77 0 0 1 4.48-3.3z" />
          </svg>
          Continue with Google (coming soon)
        </button>
        <p className="text-center text-sm text-slate-500">
          Don't have an account?{" "}
          <Link to="/register" className="text-indigo-600 font-medium hover:text-indigo-700">
            Sign up
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}

export function Register() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    if (!agreed) {
      setError("Please agree to the Terms of Service to continue.");
      return;
    }
    setIsLoading(true);
    try {
      const result = await register(email, password, name);
      setSuccess(result.detail);
      // Apres 3 secondes, rediriger vers login
      setTimeout(() => navigate("/login"), 3000);
    } catch (err: any) {
      const data = err?.response?.data;
      if (data?.email) setError(data.email[0]);
      else if (data?.password) setError(data.password[0]);
      else if (data?.detail) setError(data.detail);
      else setError("Registration failed. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthShell title="Create your account" subtitle="Start monitoring your digital presence for free">
      <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
        {error && (
          <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
            {error}
          </div>
        )}
        {success && (
          <div className="px-3 py-2 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700">
            <p className="font-medium">Account created!</p>
            <p>{success}</p>
            <p className="mt-1 text-xs text-emerald-600">Redirecting to login...</p>
          </div>
        )}
        <Input label="Full name" placeholder="Maria Schmidt" value={name} onChange={setName} />
        <Input label="Email address" type="email" placeholder="you@example.com" value={email} onChange={setEmail} />
        <Input label="Password" type="password" placeholder="Min. 12 characters" value={password} onChange={setPassword} />
        <div className="flex items-start gap-2 mt-1">
          <input
            type="checkbox"
            id="agree"
            className="mt-0.5"
            checked={agreed}
            onChange={(e) => setAgreed(e.target.checked)}
          />
          <label htmlFor="agree" className="text-xs text-slate-500">
            I agree to the{" "}
            <a href="#" className="text-indigo-600">Terms of Service</a>{" "}
            and{" "}
            <a href="#" className="text-indigo-600">Privacy Policy</a>
          </label>
        </div>
        <Button type="submit" className="w-full" disabled={isLoading || !!success}>
          {isLoading ? "Creating account..." : "Create account"}
        </Button>
        <p className="text-center text-sm text-slate-500">
          Already have an account?{" "}
          <Link to="/login" className="text-indigo-600 font-medium hover:text-indigo-700">
            Sign in
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);
    try {
      const { default: api } = await import("../services/api");
      await api.post("/auth/password/reset/", { email });
      setSent(true);
    } catch {
      setError("Failed to send reset email. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthShell title="Reset your password" subtitle="We'll send you a link to reset your password">
      <Link to="/login" className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mb-4">
        <ArrowLeft size={14} /> Back to sign in
      </Link>
      {sent ? (
        <div className="text-center py-4">
          <div className="w-12 h-12 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="text-2xl">📧</span>
          </div>
          <p className="font-semibold text-slate-900 mb-2">Check your email</p>
          <p className="text-sm text-slate-500">
            We've sent a password reset link to <strong>{email}</strong>
          </p>
        </div>
      ) : (
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          {error && (
            <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
              {error}
            </div>
          )}
          <Input
            label="Email address"
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={setEmail}
          />
          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? "Sending..." : "Send reset link"}
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
