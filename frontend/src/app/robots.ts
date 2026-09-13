import type { MetadataRoute } from "next";
import { SITE_URL, absoluteUrl } from "@/lib/seo";

/**
 * robots.txt
 *
 * Everything public is crawlable; the signed-in product is not. The disallows
 * below are not a security measure — those routes are protected by
 * authentication server-side — they exist so a crawler does not spend its budget
 * on pages that will only ever return a redirect to the sign-in screen.
 *
 * Preview and staging deployments disallow everything. A staging copy that gets
 * indexed competes with production for the same queries, and the usual way that
 * happens is exactly this file being written for production only.
 */

const IS_PRODUCTION =
  process.env.VERCEL_ENV === "production" ||
  (!process.env.VERCEL_ENV && process.env.NODE_ENV === "production");

export default function robots(): MetadataRoute.Robots {
  if (!IS_PRODUCTION) {
    return { rules: [{ userAgent: "*", disallow: "/" }] };
  }

  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [
          "/api/",
          "/dashboard",
          "/dashboard/",
          "/staff",
          "/staff/",
          "/login",
          "/signup",
          "/verify-email",
          "/reset-password",
          // Search result pages: infinite URL space, no unique content.
          "/blog?q=",
        ],
      },
    ],
    sitemap: absoluteUrl("/sitemap.xml"),
    host: SITE_URL,
  };
}
