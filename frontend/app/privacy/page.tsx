import LegalLayout from "@/components/LegalLayout";

export default function PrivacyPage() {
  return (
    <LegalLayout title="Privacy Policy" lastUpdated="July 29, 2026">
      <section>
        <h2>What we collect</h2>
        <p>
          When you upload a bank or card statement (PDF or CSV), we parse it to extract
          transactions — date, description, amount, and which account it came from. We also
          store the email address and password (hashed, never in plain text) you sign up with.
          We don&apos;t collect anything beyond what&apos;s needed to run the product: no bank
          login credentials, no location data, no device fingerprinting.
        </p>
      </section>

      <section>
        <h2>How we store it</h2>
        <p>
          Transaction descriptions are encrypted at rest (Fernet/AES-128) and only decrypted
          in memory when needed to answer your questions or show your ledger. Uploaded statement
          files are processed in memory to extract transactions and are not retained afterward.
          Every record is scoped to your account — other users can never see your data.
        </p>
      </section>

      <section>
        <h2>Third parties</h2>
        <p>
          Transaction categorization and the AskCFO chat feature call Anthropic&apos;s API to
          process your transaction data and questions. This data is sent solely to generate a
          response to you and is not used to train Anthropic&apos;s models. We don&apos;t sell
          your data to anyone, and we don&apos;t use it for advertising.
        </p>
      </section>

      <section>
        <h2>Your rights</h2>
        <p>
          You can request a copy of your data or ask us to delete your account and everything
          tied to it at any time by emailing{" "}
          <a href="mailto:hello@personalcfo.app" className="text-blue-600 hover:underline">
            hello@personalcfo.app
          </a>
          .
        </p>
      </section>

      <section>
        <h2>Security practices</h2>
        <p>
          Passwords are hashed with bcrypt and never stored in plain text. Sessions use
          short-lived signed tokens. Sensitive fields are encrypted at rest. We don&apos;t log
          transaction descriptions, amounts, or the content of your questions and answers.
        </p>
      </section>

      <section>
        <h2>Contact</h2>
        <p>
          Questions about this policy:{" "}
          <a href="mailto:hello@personalcfo.app" className="text-blue-600 hover:underline">
            hello@personalcfo.app
          </a>
          .
        </p>
      </section>
    </LegalLayout>
  );
}
