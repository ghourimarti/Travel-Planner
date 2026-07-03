import { Footer } from "@/components/site/footer";
import { Navbar } from "@/components/site/navbar";
import { SiteHeader } from "@/components/site/site-header";
import { authMode, getCurrentUser, loginPath, logoutPath, signupPath } from "@/lib/auth";

export default async function MarketingLayout({ children }: { children: React.ReactNode }) {
  const user = await getCurrentUser();
  return (
    <div className="flex min-h-screen flex-col">
      {/* Signed-in visitors get the SAME app navbar everywhere; logged-out get the marketing nav. */}
      {user ? (
        <SiteHeader mode={authMode} logoutHref={logoutPath} />
      ) : (
        <Navbar user={null} loginHref={loginPath} signupHref={signupPath} logoutHref={logoutPath} />
      )}
      <main className="flex-1">{children}</main>
      <Footer />
    </div>
  );
}
