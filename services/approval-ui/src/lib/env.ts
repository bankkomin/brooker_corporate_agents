import { z } from "zod";

const envSchema = z.object({
  NEXT_PUBLIC_GATEWAY_URL: z.string().url("NEXT_PUBLIC_GATEWAY_URL must be a valid URL"),
  NEXT_PUBLIC_PORTAL_API_URL: z.string().default("http://localhost:5112"),
});

export const env = envSchema.parse({
  NEXT_PUBLIC_GATEWAY_URL: process.env.NEXT_PUBLIC_GATEWAY_URL,
  NEXT_PUBLIC_PORTAL_API_URL: process.env.NEXT_PUBLIC_PORTAL_API_URL,
});
