import { Footer } from "@/components/site/footer";
import { Navbar } from "@/components/site/navbar";
import { getCurrentUser, loginPath, logoutPath, signupPath } from "@/lib/auth";

export default async function MarketingLayout({ children }: { children: React.ReactNode }) {
  const user = await getCurrentUser();
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar
        user={user}
        loginHref={loginPath}
        signupHref={signupPath}
        logoutHref={logoutPath}
      />
      <main className="flex-1">{children}</main>
      <Footer />
    </div>
  );
}
