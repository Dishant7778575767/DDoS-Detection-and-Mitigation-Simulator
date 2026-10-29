import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const baseUrl = process.env.NEXT_PUBLIC_APP_URL || "https://sentrix.security";

  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/overview"],
        disallow: [
          "/telemetry",
          "/threats",
          "/alerts",
          "/mitigation",
          "/simulator",
          "/history",
          "/settings",
          "/api/",
        ],
      },
    ],
    sitemap: `${baseUrl}/sitemap.xml`,
  };
}

