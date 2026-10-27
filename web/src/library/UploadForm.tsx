import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { api } from "../api/client";
import type { Refusal } from "./library.constants";
import { bookAnchor, refusalFor } from "./library.constants";
import type { Upload } from "./library.schema";
import { uploadSchema } from "./library.schema";

export interface UploadFormProps {
  onUploaded: () => void;
}

export function UploadForm({ onUploaded }: UploadFormProps) {
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const { register, handleSubmit, formState, reset } = useForm<Upload>({
    resolver: zodResolver(uploadSchema),
  });

  const submit = handleSubmit(async ({ files }) => {
    const file = files[0];
    const { error } = await api.POST("/api/books", {
      // The schema types a file part as a string, so the serializer sends the real file.
      body: { file: file.name },
      bodySerializer: () => {
        const form = new FormData();
        form.append("file", file);
        return form;
      },
    });
    if (error) {
      setRefusal(refusalFor(error));
      return;
    }
    setRefusal(null);
    reset();
    onUploaded();
  });

  return (
    <form onSubmit={submit} noValidate>
      <label>
        Book file
        <input type="file" accept=".epub,.pdf,application/epub+zip,application/pdf" {...register("files")} />
      </label>
      {formState.errors.files && <p>{formState.errors.files.message}</p>}
      {refusal && (
        <p role="alert">
          {refusal.message}
          {refusal.book && (
            <>
              {": "}
              <a href={`#${bookAnchor(refusal.book.id)}`}>{refusal.book.title}</a>
            </>
          )}
        </p>
      )}
      <button type="submit" disabled={formState.isSubmitting}>
        Upload
      </button>
    </form>
  );
}
