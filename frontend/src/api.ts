export async function apiGet(path: string) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(await r.text());
  return await r.json();
}

export async function apiPost(path: string, body: any) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return await r.json();
}
