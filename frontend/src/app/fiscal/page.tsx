import { redirect } from "next/navigation";

export default function LegacyFiscalRedirect() {
  redirect("/accounting");
}
