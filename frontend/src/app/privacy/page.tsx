import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Política de Privacidad — Comerciante P2P",
  description:
    "Política de privacidad y uso limitado de datos de APIs de Google en Comerciante P2P (sistemap2pmerchant.com).",
};

export default function PrivacyPolicyPage() {
  const supportEmail =
    process.env.NEXT_PUBLIC_SUPPORT_EMAIL || "soporte@sistemap2pmerchant.com";

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
          <h1 className="text-2xl font-bold text-white">
            Política de Privacidad / Privacy Policy
          </h1>
          <p className="text-xs text-slate-400 font-mono">
            Última actualización / Last updated: 25 de noviembre de 2026
          </p>
        </header>

        <section className="space-y-2 text-sm leading-relaxed text-slate-300">
          <h2 className="text-base font-semibold text-white">1. Responsable y Alcance</h2>
          <p>
            <strong>Comerciante P2P</strong> (accesible en{" "}
            <span className="font-mono text-amber-300">https://sistemap2pmerchant.com</span>) es una
            plataforma de gestión operativa, conciliación bancaria y reportes contables para
            comerciantes P2P. Esta política describe con exactitud qué datos de usuario de Google
            accedemos, cómo los usamos, protegemos, retenemos y eliminamos al conectar Google
            OAuth 2.0.
          </p>
        </section>

        <section className="space-y-2 text-sm leading-relaxed text-slate-300">
          <h2 className="text-base font-semibold text-white">
            2. Acceso a Datos de Usuario de Google (Data Access)
          </h2>
          <p>
            La vinculación con Google es completamente opcional. Cuando un usuario autoriza Google
            OAuth 2.0 en <span className="font-mono">/sheets</span>, solicitamos únicamente los
            siguientes permisos y datos:
          </p>
          <ul className="list-disc pl-5 space-y-1.5">
            <li>
              <strong>
                <span className="font-mono">openid</span> y <span className="font-mono">email</span>:
              </strong>{" "}
              accedemos exclusivamente a la dirección de correo electrónico de la cuenta de Google
              conectada para mostrar al usuario qué cuenta se encuentra vinculada.
            </li>
            <li>
              <strong>
                <span className="font-mono">https://www.googleapis.com/auth/drive.file</span>:
              </strong>{" "}
              permite crear una hoja de cálculo contable dedicada en el Google Drive del usuario si
              este no ha vinculado una hoja existente.
            </li>
            <li>
              <strong>
                <span className="font-mono">https://www.googleapis.com/auth/spreadsheets</span>:
              </strong>{" "}
              permite escribir y actualizar las pestañas contables (Resumen Fiscal, Órdenes P2P,
              Libro Diario y Libro Mayor) únicamente en la hoja de cálculo específica cuyo enlace o
              ID el propio usuario configuró en <span className="font-mono">/sheets</span>,
              incluyendo hojas contables preexistentes creadas por el usuario fuera de la aplicación.
            </li>
            <li>
              <strong>Sin datos agregados ni escaneo de Drive:</strong> no leemos, indexamos,
              copiamos ni generamos conjuntos de datos agregados o anonimizados a partir de otros
              archivos, documentos o correos de la cuenta de Google del usuario.
            </li>
          </ul>
        </section>

        <section className="space-y-2 text-sm leading-relaxed text-slate-300">
          <h2 className="text-base font-semibold text-white">
            3. Uso y No Transferencia de Datos de Google (Data Use &amp; Transfer)
          </h2>
          <ul className="list-disc pl-5 space-y-1.5">
            <li>
              <strong>Uso exclusivo de la función solicitada:</strong> los datos de usuario de Google
              (correo y tokens OAuth) y el acceso a la hoja vinculada se utilizan únicamente para
              ejecutar la exportación y sincronización contable iniciada explícitamente por el
              usuario en <span className="font-mono">/sheets</span>.
            </li>
            <li>
              <strong>Cero transferencia o venta a terceros:</strong> no transferimos, compartimos,
              alquilamos ni vendemos datos de usuario de Google (ni en bruto ni agregados/anonimizados)
              a terceros, anunciantes, corredores de datos, entidades crediticias ni redes de
              publicidad. Tampoco se utilizan con fines de publicidad dirigida ni evaluación
              crediticia.
            </li>
          </ul>
        </section>

        <section className="space-y-2 text-sm leading-relaxed text-slate-300">
          <h2 className="text-base font-semibold text-white">
            4. Cumplimiento de Uso Limitado y Restricción de IA/ML (Limited Use &amp; AI/ML Policy)
          </h2>
          <p className="p-3.5 rounded-xl bg-[#0b0e14] border border-amber-400/25 text-slate-200">
            The use of raw or derived user data received from Google Workspace APIs will adhere to
            the{" "}
            <a
              href="https://developers.google.com/terms/api-services-user-data-policy"
              target="_blank"
              rel="noopener noreferrer"
              className="text-amber-400 underline hover:text-amber-300"
            >
              Google API Services User Data Policy
            </a>
            , including the Limited Use requirements.
          </p>
          <ul className="list-disc pl-5 space-y-1.5">
            <li>
              <strong>Prohibición absoluta de entrenamiento IA/ML:</strong> ningún dato de usuario
              obtenido de las APIs de Google Workspace (en bruto, derivado o anonimizado) es
              utilizado para desarrollar, mejorar o entrenar modelos de inteligencia artificial o
              aprendizaje automático (ni generalizados ni personalizados).
            </li>
            <li>
              <strong>Sin envío a servicios de IA de terceros:</strong> aunque la aplicación cuenta
              con módulos independientes para lectura OCR de comprobantes bancarios y consultas de
              Telegram, los datos provenientes de Google OAuth, Google Drive y Google Sheets{" "}
              <strong>nunca</strong> se transfieren ni se envían a proveedores de IA/ML de terceros.
            </li>
          </ul>
        </section>

        <section className="space-y-2 text-sm leading-relaxed text-slate-300">
          <h2 className="text-base font-semibold text-white">
            5. Protección y Seguridad de los Datos (Data Protection)
          </h2>
          <ul className="list-disc pl-5 space-y-1.5">
            <li>
              Todas las comunicaciones entre el navegador, la plataforma y las APIs de Google se
              transmiten exclusivamente mediante cifrado <strong>HTTPS/TLS</strong>.
            </li>
            <li>
              Los tokens OAuth de Google y claves API del usuario se almacenan cifrados en reposo
              mediante <strong>AES-256-GCM</strong> con aislamiento estricto por usuario y estado
              anti-CSRF firmado con <strong>HMAC-SHA256</strong>.
            </li>
            <li>
              Las contraseñas y códigos de verificación se protegen mediante hashes criptográficos
              irreversibles y nunca se registran secretos ni tokens en logs o interfaces.
            </li>
          </ul>
        </section>

        <section className="space-y-2 text-sm leading-relaxed text-slate-300">
          <h2 className="text-base font-semibold text-white">
            6. Retención, Revocación y Eliminación de Datos (Data Retention &amp; Deletion)
          </h2>
          <ul className="list-disc pl-5 space-y-1.5">
            <li>
              <strong>Retención de tokens de Google:</strong> el correo vinculado y el refresh token
              cifrado se conservan únicamente mientras el usuario mantenga activa la integración de
              Google Sheets. No almacenamos copias locales de hojas de cálculo de Google Drive.
            </li>
            <li>
              <strong>Eliminación inmediata al desconectar:</strong> al pulsar{" "}
              <strong>Desconectar</strong> en <span className="font-mono">/sheets</span>, el token
              cifrado y el correo de Google asociados se eliminan inmediatamente de nuestra base de
              datos. También puedes revocar el acceso en cualquier momento desde{" "}
              <a
                href="https://myaccount.google.com/permissions"
                target="_blank"
                rel="noopener noreferrer"
                className="text-amber-400 underline hover:text-amber-300"
              >
                myaccount.google.com/permissions
              </a>
              .
            </li>
            <li>
              <strong>Eliminación total de cuenta:</strong> los datos operativos propios de la cuenta
              se conservan mientras la cuenta permanezca activa. Para solicitar la eliminación
              definitiva de tu cuenta y todos tus registros, escribe desde tu correo registrado a{" "}
              <a
                href={`mailto:${supportEmail}`}
                className="text-amber-400 underline hover:text-amber-300 font-mono"
              >
                {supportEmail}
              </a>
              ; procesamos la eliminación completa en un plazo máximo de <strong>30 días</strong>.
            </li>
          </ul>
        </section>

        <section className="space-y-2 text-xs leading-relaxed text-slate-400 border-t border-[#1e2430] pt-5">
          <h2 className="text-sm font-semibold text-white">
            English Compliance Summary (Google OAuth Verification)
          </h2>
          <p>
            <strong>Data Access &amp; Use:</strong> Comerciante P2P (sistemap2pmerchant.com) accesses
            only the user&apos;s Google email (<span className="font-mono">openid</span>,{" "}
            <span className="font-mono">email</span>) and the user-designated spreadsheet via{" "}
            <span className="font-mono">drive.file</span> and{" "}
            <span className="font-mono">spreadsheets</span> solely to create or update the
            user&apos;s own P2P accounting sheets when triggered by the user in{" "}
            <span className="font-mono">/sheets</span>.
          </p>
          <p>
            <strong>No Third-Party Transfer &amp; No AI/ML Training:</strong> Raw or derived Google
            user data is never sold, shared, or transferred to third parties, advertisers, or
            third-party AI/ML services, and is never used to develop, improve, or train AI/ML models.
          </p>
          <p>
            <strong>Security, Retention &amp; Deletion:</strong> OAuth tokens are encrypted at rest
            with AES-256-GCM over HTTPS/TLS, retained only while connected, and purged immediately
            upon clicking Disconnect in <span className="font-mono">/sheets</span> or revoking access
            at Google Account Permissions. Full account deletion requests sent to{" "}
            <span className="font-mono text-slate-300">{supportEmail}</span> are completed within 30
            days.
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
