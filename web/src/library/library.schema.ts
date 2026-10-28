import { z } from "zod";

export const uploadSchema = z.object({
  files: z.custom<FileList>((value) => value instanceof FileList && value.length === 1, "Choose a file"),
});

export type Upload = z.infer<typeof uploadSchema>;
