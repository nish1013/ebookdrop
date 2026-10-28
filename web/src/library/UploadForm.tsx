import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { api } from "../api/client";
import { Alert } from "../ui/alert";
import { Button } from "../ui/button";
import { Card, CardContent } from "../ui/card";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
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
    <Card className="mb-8 border-dashed">
      <CardContent className="pt-6">
        <form onSubmit={submit} noValidate className="grid gap-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <Label className="flex-1">
              Book file
              <Input type="file" accept=".epub,.pdf,application/epub+zip,application/pdf" {...register("files")} />
            </Label>
            <Button type="submit" disabled={formState.isSubmitting}>
              Upload
            </Button>
          </div>
          {formState.errors.files && <p className="text-sm text-destructive">{formState.errors.files.message}</p>}
          {refusal && (
            <Alert variant="destructive">
              {refusal.message}
              {refusal.book && (
                <>
                  {": "}
                  <a href={`#${bookAnchor(refusal.book.id)}`} className="font-medium underline underline-offset-4">
                    {refusal.book.title}
                  </a>
                </>
              )}
            </Alert>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
