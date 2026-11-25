import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Política de Privacidad — Comerciante P2P",
  description:
    "Política de privacidad y uso limitado de datos de APIs de Google en Comerciante P2P (sistemap2pmerchant.com).",
};

export default function PrivacyPolicyPage() {
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
          <h1 className="text-2xl font-bold text-white">Política de Privacidad</h1>
          <p className="text-xs text-slate-400 font-mono">
            Última actualización: 24 de noviembre de 2026
          </p>
        </header>

        <section className="space-y-2 text-sm leading-relaxed text-slate-300">
          <h2 className="text-base font-semibold text-white">1. Responsable y Alcance</h2>
          <p>
            <strong>Comerciante P2P</strong> (accesible en{" "}
            <span className="font-mono text-amber-300">https://sistemap2pmerchant.com</span>) es una
            plataforma privada de gestión operativa, conciliación bancaria y reportes contables para
            operadores P2P. Esta política explica qué datos recopilamos, cómo los protegemos y cómo
            utilizamos la información autorizada mediante Google OAuth 2.0.
          </p>
        </section>

        <section className="space-y-2 text-sm leading-relaxed text-slate-300">
          <h2 className="text-base font-semibold text-white">2. Datos que Recopilamos</h2>
          <ul className="list-disc pl-5 space-y-1.5">
            <li>
              <strong>Datos de cuenta:</strong> nombre o alias, correo electrónico (verificado
              mediante código OTP), identificador fiscal opcional (Cédula/RIF para encabezados de
              reportes) e ID de Telegram para notificaciones de seguridad.
            </li>
            <li>
              <strong>Datos operativos y contables:</strong> historial de órdenes P2P sincronizadas o
              importadas por el usuario, comprobantes bancarios cargados para conciliación y saldos
              contables registrados voluntariamente por el titular.
            </li>
            <li>
              <strong>Datos de Google OAuth 2.0 (solo si el usuario lo conecta):</strong> dirección
              de correo de Google y tokens de acceso/actualización necesarios únicamente para crear o
              actualizar las hojas de cálculo de Google Sheets autorizadas por el usuario.
            </li>
          </ul>
        </section>

        <section className="space-y-2 text-sm leading-relaxed text-slate-300">
          <h2 className="text-base font-semibold text-white">
            3. Uso Limitado de Datos de APIs de Google (Google API Services User Data Policy)
          </h2>
          <p>
            El uso y la transferencia por parte de <strong>Comerciante P2P</strong> de información
            recibida de las APIs de Google a cualquier otra aplicación cumple estrictamente con la{" "}
            <a
              href="https://developers.google.com/terms/api-services-user-data-policy"
              target="_blank"
              rel="noopener noreferrer"
              className="text-amber-400 underline hover:text-amber-300"
            >
              Google API Services User Data Policy
            </a>
            , incluidos los requisitos de <strong>Uso Limitado (Limited Use)</strong>.
          </p>
          <ul className="list-disc pl-5 space-y-1.5">
            <li>
              Solo accedemos a <strong>Google Sheets / Google Drive</strong> para escribir o crear la
              hoja contable que el propio usuario vincula en el módulo{" "}
              <span className="font-mono">/sheets</span>.
            </li>
            <li>
              No leemos, copiamos ni indexamos archivos ajenos de Google Drive del usuario.
            </li>
            <li>
              No vendemos, alquilamos ni compartimos datos de Google con terceros, redes publicitarias
              ni modelos de inteligencia artificial generalizados.
            </li>
          </ul>
        </section>

        <section className="space-y-2 text-sm leading-relaxed text-slate-300">
          <h2 className="text-base font-semibold text-white">4. Seguridad y Almacenamiento</h2>
          <p>
            Las contraseñas, códigos OTP y respuestas de recuperación se almacenan exclusivamente
            mediante hashes criptográficos irreversibles. Las claves API y tokens de actualización de
            Google OAuth se cifran en reposo con <strong>AES-256-GCM</strong> y se transmiten
            exclusivamente bajo HTTPS/TLS.
          </p>
        </section>

        <section className="space-y-2 text-sm leading-relaxed text-slate-300">
          <h2 className="text-base font-semibold text-white">
            5. Revocación de Acceso y Eliminación de Datos
          </h2>
          <p>
            El usuario puede desconectar su cuenta de Google en cualquier momento desde la sección{" "}
            <span className="font-mono">/sheets</span> de la aplicación (lo que elimina de inmediato el
            token cifrado almacenado), o revocar el acceso directamente desde{" "}
            <a
              href="https://myaccount.google.com/permissions"
              target="_blank"
              rel="noopener noreferrer"
              className="text-amber-400 underline hover:text-amber-300"
            >
              myaccount.google.com/permissions
            </a>
            . Para solicitar la eliminación completa de su cuenta y datos asociados, puede escribir al
            administrador de la plataforma desde su correo registrado.
          </p>
        </section>

        <footer className="border-t border-[#1e2430] pt-4 flex items-center justify-between text-xs text-slate-400 flex-wrap gap-2">
          <span>© 2026 Comerciante P2P · sistemap2pmerchant.com</span>
          <Link href="/terms" className="text-amber-400 hover:underline">
            Ver Condiciones del Servicio →
          </Link>
        </footer>
      </article>
    </div>
  );
}
