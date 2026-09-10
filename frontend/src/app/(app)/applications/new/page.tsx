"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { useSession } from "@/lib/auth/SessionProvider";
import { createApplication, listSchools } from "@/lib/applications";
import { Alert, BackLink, Button, Field, inputClass } from "@/components/ui";

interface SchoolOption {
  id: string;
  name: string;
  country_name: string | null;
  programmes: { id: string; name: string; intakes: string[] }[];
}

export default function NewApplicationPage() {
  const router = useRouter();
  const { session, loading, hasAccess } = useSession();
  const [schools, setSchools] = useState<SchoolOption[]>([]);
  const [schoolId, setSchoolId] = useState("");
  const [programmeId, setProgrammeId] = useState("");
  const [intake, setIntake] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (!session) return router.replace("/login");
    if (!hasAccess) return router.replace("/checkout");
    listSchools()
      .then((page) => setSchools(page.results))
      .catch(() => setError("We couldn't load the school list. Please refresh."));
  }, [loading, session, hasAccess, router]);

  const school = schools.find((s) => s.id === schoolId);
  const programme = school?.programmes.find((p) => p.id === programmeId);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const application = await createApplication({
        school: schoolId,
        programme: programmeId || undefined,
        intake,
      });
      router.push(`/applications/${application.id}`);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? (Object.values(err.fieldErrors)[0]?.[0] ?? err.message)
          : "We couldn't start this application. Try again.",
      );
      setBusy(false);
    }
  }

  if (loading) return <div className="p-12 text-sm text-subtle">Loading…</div>;

  return (
    <div className="mx-auto max-w-md px-6 py-12">
      <BackLink href="/dashboard">Back to my applications</BackLink>
      <h1 className="mt-4 text-2xl font-semibold text-ink">Add a school</h1>
      <p className="mt-1 text-sm text-muted">
        We&apos;ll build your checklist from this school&apos;s actual requirements. You can apply
        to as many schools as you like — each gets its own checklist.
      </p>

      <form onSubmit={submit} className="mt-8 space-y-5">
        {error && <Alert>{error}</Alert>}

        <Field label="School" htmlFor="school">
          <select
            id="school"
            required
            value={schoolId}
            onChange={(e) => {
              setSchoolId(e.target.value);
              setProgrammeId("");
              setIntake("");
            }}
            className={inputClass}
          >
            <option value="">Select a school…</option>
            {schools.map((option) => (
              <option key={option.id} value={option.id}>
                {option.name}
                {option.country_name ? ` — ${option.country_name}` : ""}
              </option>
            ))}
          </select>
        </Field>

        {school && school.programmes.length > 0 && (
          <Field label="Course" htmlFor="programme">
            <select
              id="programme"
              value={programmeId}
              onChange={(e) => {
                setProgrammeId(e.target.value);
                setIntake("");
              }}
              className={inputClass}
            >
              <option value="">Not sure yet</option>
              {school.programmes.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.name}
                </option>
              ))}
            </select>
          </Field>
        )}

        <Field
          label="Intake"
          htmlFor="intake"
          hint="Which start date you're aiming for, e.g. October 2027."
        >
          {programme && programme.intakes.length > 0 ? (
            <select
              id="intake"
              required
              value={intake}
              onChange={(e) => setIntake(e.target.value)}
              className={inputClass}
            >
              <option value="">Select an intake…</option>
              {programme.intakes.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          ) : (
            <input
              id="intake"
              required
              placeholder="October 2027"
              value={intake}
              onChange={(e) => setIntake(e.target.value)}
              className={inputClass}
            />
          )}
        </Field>

        <Button type="submit" disabled={busy || !schoolId} className="w-full">
          {busy ? "Setting up your checklist…" : "Start this application"}
        </Button>
      </form>
    </div>
  );
}
