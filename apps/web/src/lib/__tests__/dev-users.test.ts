import { randomUUID } from "node:crypto";
import { promises as fs } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { createDevUser, findDevUser, verifyDevUser } from "@/lib/dev-users";

let file: string;

beforeEach(() => {
  file = path.join(tmpdir(), `voyantra-devusers-${randomUUID()}.json`);
  process.env.DEV_USERS_FILE = file;
});

afterEach(async () => {
  delete process.env.DEV_USERS_FILE;
  await fs.rm(file, { force: true });
});

describe("dev user store", () => {
  it("creates a user and verifies the right password (and rejects the wrong one)", async () => {
    const created = await createDevUser({ name: "Ada", email: "Ada@Example.com", password: "secret123" });
    expect("error" in created).toBe(false);

    expect(await verifyDevUser("ada@example.com", "secret123")).not.toBeNull();
    expect(await verifyDevUser("ada@example.com", "wrong")).toBeNull();
  });

  it("normalizes email and rejects duplicates", async () => {
    await createDevUser({ name: "A", email: "dup@example.com", password: "secret123" });
    const again = await createDevUser({ name: "B", email: "DUP@example.com", password: "secret123" });
    expect("error" in again).toBe(true);
    expect(await findDevUser("dup@example.com")).not.toBeNull();
  });

  it("does not store the password in plaintext", async () => {
    await createDevUser({ name: "C", email: "c@example.com", password: "plaintextpw" });
    const raw = await fs.readFile(file, "utf8");
    expect(raw).not.toContain("plaintextpw");
  });
});
