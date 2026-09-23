import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Surface } from "@/components/layout/surface";
import { useCreateTest } from "../use-tests";

/** Name-only creation entry point; the rest of the configuration is incremental. */
export function TestCreatePage() {
  const navigate = useNavigate();
  const createTest = useCreateTest();
  const [name, setName] = useState("");

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!name.trim()) return;
    try {
      const test = await createTest.mutateAsync({ name: name.trim() });
      navigate(`/tests/${test.test_definition_id}/edit`);
    } catch {
      // Mutation error is rendered below.
    }
  };

  return (
    <Page>
      <Page.Header
        title="Create test"
        description="Start with a name. Benchmark, target, and metrics can be configured later."
        breadcrumbs={[{ label: "Tests", href: "/tests" }]}
      />
      <Page.Content>
        <div className="mx-auto max-w-2xl">
          <Surface className="p-5">
            <form className="space-y-5" onSubmit={(event) => void submit(event)}>
              <Input
                autoFocus
                label="Test name"
                value={name}
                placeholder="e.g. Production grounding regression"
                onChange={(event) => {
                  setName(event.target.value);
                }}
              />
              <p className="text-xs text-text-tertiary">
                Only the name is required to create an editable test.
              </p>
              {createTest.error && (
                <Alert variant="error">
                  <AlertDescription>{createTest.error.message}</AlertDescription>
                </Alert>
              )}
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    navigate("/tests");
                  }}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  loading={createTest.isPending}
                  disabled={!name.trim()}
                >
                  Create Test
                </Button>
              </div>
            </form>
          </Surface>
        </div>
      </Page.Content>
    </Page>
  );
}
