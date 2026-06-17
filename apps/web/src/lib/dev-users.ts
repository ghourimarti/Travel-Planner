/**
 * File-backed dev user store (S13a-auth) for the keyless dev login. Real
 * accounts with salted scrypt-hashed passwords, persisted to a JSON file
 * (gitignored). This stands in for Auth0's user database in local/demo mode;
 * when Auth0 is configured, none of this runs.
 */
import "server-only";

import { randomBytes, scrypt, timingSafeEqual } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";
import { promisify } from "node:util";

const scryptAsync = promisify(scrypt) as (
  password: string | Buffer,
  salt: string | Buffer,
  keylen: number,
) => Promise<Buffer>;

export interface DevUser {
  name: string;
  email: string;
  salt: string;
  hash: string;
  createdAt: number;
}

function storeFile(): string {
  return process.env.DEV_USERS_FILE ?? path.join(process.cwd(), ".dev-users.json");
}

function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}

async function readAll(): Promise<DevUser[]> {
  try {
    return JSON.parse(await fs.readFile(storeFile(), "utf8")) as DevUser[];
  } catch {
    return [];
  }
}

async function writeAll(users: DevUser[]): Promise<void> {
  await fs.writeFile(storeFile(), JSON.stringify(users, null, 2), "utf8");
}

async function hashPassword(password: string, salt: string): Promise<string> {
  return (await scryptAsync(password, salt, 64)).toString("hex");
}

export async function findDevUser(email: string): Promise<DevUser | null> {
  const e = normalizeEmail(email);
  return (await readAll()).find((u) => u.email === e) ?? null;
}

export async function createDevUser(input: {
  name: string;
  email: string;
  password: string;
}): Promise<DevUser | { error: string }> {
  const email = normalizeEmail(input.email);
  const all = await readAll();
  if (all.some((u) => u.email === email)) {
    return { error: "An account with that email already exists." };
  }
  const salt = randomBytes(16).toString("hex");
  const hash = await hashPassword(input.password, salt);
  const user: DevUser = {
    name: input.name.trim() || email.split("@")[0],
    email,
    salt,
    hash,
    createdAt: Date.now(),
  };
  all.push(user);
  await writeAll(all);
  return user;
}

export async function verifyDevUser(email: string, password: string): Promise<DevUser | null> {
  const user = await findDevUser(email);
  if (!user) return null;
  const candidate = Buffer.from(await hashPassword(password, user.salt), "hex");
  const expected = Buffer.from(user.hash, "hex");
  if (candidate.length !== expected.length || !timingSafeEqual(candidate, expected)) return null;
  return user;
}
