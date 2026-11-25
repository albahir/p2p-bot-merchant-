import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Condiciones del Servicio — Comerciante P2P",
  description:
    "Condiciones de uso y responsabilidades de la plataforma Comerciante P2P (sistemap2pmerchant.com).",
};

export default function TermsOfServicePage() {
  return (
    <div className="min-h-screen bg-[#0b0e14] text-slate-200 px-4 py-10 sm:px-6 lg:px-8">
      <article className="max-w-3xl mx-auto rounded-2xl bg-[#111620] border border-[#1e2430] p-6 sm:p-10 space-y-6">
        <header className="border-b border-[#1e2430] pb-5 space-y-2">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <span className="text-xs font-mono uppercase tracking-wider text-amber-400">
              sistemap2pmerchant.com
            </span>
            <Link
              href="/"
              className="text-xs font-mono text-slate-400 hover:text-white underline"
            >
              ← Volver a la aplicación
            </Link>
          </div>
          <h1 className="text-2xl font-bold text-white">Condiciones del Servicio</h1>
          <p className="text-xs text-slate-400 font-mono">
            Última actualización: 24 de noviembre de 2026
          </p>
        </header>

        <section className="space-y-2 text-sm leading-relaxed text-slate-300">
          <h2 className="text-base font-semibold text-white">1. Aceptación y Naturaleza del Servicio</h2>
          <p>
            Al acceder y utilizar <strong>Comerciante P2P</strong> (
            <span className="font-mono text-amber-300">https://sistemap2pmerchant.com</span>), aceptas
            estas Condiciones del Servicio. La plataforma proporciona herramientas de monitoreo de
            mercado, cálculo de rentabilidad, conciliación bancaria y generación de reportes contables
            de apoyo. <strong>No custodiamos fondos</strong>, no ejecutamos retiros bancarios ni
            prestamos asesoría financiera, legal o tributaria certificada.
          </p>
        </section>

        <section className="space-y-2 text-sm leading-relaxed text-slate-300">
          <h2 className="text-base font-semibold text-white">2. Credenciales y Seguridad de la Cuenta</h2>
          <ul className="list-disc pl-5 space-y-1.5">
            <li>
              El usuario es responsable de resguardar su contraseña, llave maestra de recuperación y
              acceso a su correo y cuenta de Telegram.
            </li>
            <li>
              Al conectar claves API de exchanges externos (como Binance), el usuario debe configurar
              exclusivamente permisos mínimos (<strong>Lectura y P2P</strong>, nunca retiros) y lista
              blanca de IP.
            </li>
          </ul>
        </section>

        <section className="space-y-2 text-sm leading-relaxed text-slate-300">
          <h2 className="text-base font-semibold text-white">3. Integración con Google Sheets y Terceros</h2>
          <p>
            La vinculación con Google Sheets mediante OAuth 2.0 o Cuenta de Servicio es opcional y
            controlada por el usuario. La disponibilidad de APIs de terceros (Google, Binance, BCV,
            Telegram) depende de dichos proveedores externos.
          </p>
        </section>

        <section className="space-y-2 text-sm leading-relaxed text-slate-300">
          <h2 className="text-base font-semibold text-white">4. Responsabilidad Contable y Tributaria</h2>
          <p>
            Los cálculos y archivos exportados (Excel, PDF, Google Sheets) se generan a partir de los
            datos y saldos suministrados por el usuario. Es responsabilidad exclusiva del titular
            verificar dichos soportes junto a su Contador Público antes de presentar declaraciones
            ante las autoridades tributarias competentes.
          </p>
        </section>

        <section className="space-y-2 text-sm leading-relaxed text-slate-300">
          <h2 className="text-base font-semibold text-white">5. Modificaciones y Suspensión</h2>
          <p>
            Nos reservamos el derecho de actualizar estas condiciones o suspender cuentas ante uso
            indebido, intentos de acceso no autorizado o incumplimiento de medidas de seguridad.
          </p>
        </section>

        <footer className="border-t border-[#1e2430] pt-4 flex items-center justify-between text-xs text-slate-400 flex-wrap gap-2">
          <span>© 2026 Comerciante P2P · sistemap2pmerchant.com</span>
          <Link href="/privacy" className="text-amber-400 hover:underline">
            Ver Política de Privacidad →
          </Link>
        </footer>
      </article>
    </div>
  );
}
