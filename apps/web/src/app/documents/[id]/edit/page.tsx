import { notFound } from "next/navigation";
import Link from "next/link";
import { getSop } from "@/lib/sop-api";
import { EditSopForm } from "./edit-form";

export const metadata = { title: "Edit SOP — AI Operations Toolkit" };

export default async function EditSopPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let sop;
  try {
    sop = await getSop(id);
  } catch {
    notFound();
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div>
        <Link
          href={`/documents/${id}`}
          className="text-sm text-slate-500 hover:underline dark:text-slate-400"
        >
          ← Back to the SOP
        </Link>
      </div>

      <header>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          Edit: {sop.content.title}
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Saving creates version {sop.version + 1}. Version {sop.version} is kept,
          so you can compare them afterwards.
        </p>
      </header>

      <EditSopForm
        id={id}
        content={sop.content}
        metadata={sop.metadata}
        nextVersion={sop.version + 1}
      />
    </div>
  );
}
