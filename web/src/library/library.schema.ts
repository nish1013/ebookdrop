import { z } from "zod";
import { MAX_FILE_BYTES, TOO_LARGE_MESSAGE } from "./library.constants";

export const uploadSchema = z.object({
  files: z
    .custom<FileList>((value) => value instanceof FileList && value.length === 1, "Choose a file")
    .refine((files) => files[0].size <= MAX_FILE_BYTES, TOO_LARGE_MESSAGE),
});

export type Upload = z.infer<typeof uploadSchema>;
