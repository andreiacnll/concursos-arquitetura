import { NextRequest, NextResponse } from "next/server";

const SEARCHES: Record<string, string> = {
  Arquitetura: "modern architecture",
  Habitação: "modern residential architecture",
  Escolas: "contemporary school architecture",
  Saúde: "hospital architecture",
  Paisagismo: "landscape architecture",
  "Espaço público": "public square architecture",
  Património: "heritage architecture",
};

export async function GET(req: NextRequest) {
  const category = req.nextUrl.searchParams.get("category") || "Arquitetura";

  const query = SEARCHES[category] ?? "modern architecture";

  const response = await fetch(
    `https://api.pexels.com/v1/search?query=${encodeURIComponent(query)}&per_page=12`,
    {
      headers: {
        Authorization: process.env.PEXELS_API_KEY!,
      },
      cache: "force-cache",
    }
  );

  if (!response.ok) {
    return NextResponse.json({ image: null }, { status: 500 });
  }

  const data = await response.json();

  if (!data.photos?.length) {
    return NextResponse.json({ image: null });
  }

  const random =
    data.photos[Math.floor(Math.random() * data.photos.length)];

  return NextResponse.json({
    image: random.src.large2x,
    photographer: random.photographer,
  });
}
