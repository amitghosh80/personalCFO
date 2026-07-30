import LegalLayout from "@/components/LegalLayout";

export default function TermsPage() {
  return (
    <LegalLayout title="Terms of Service" lastUpdated="July 29, 2026">
      <section>
        <h2>Acceptance of terms</h2>
        <p>
          By creating an account or uploading a statement, you agree to these terms. If you
          don&apos;t agree, don&apos;t use personalCFO.
        </p>
      </section>

      <section>
        <h2>What personalCFO is</h2>
        <p>
          personalCFO is a tool for parsing, categorizing, and answering questions about
          financial statements you upload yourself. It is not a bank, is not a registered
          investment or financial advisor, and does not move money, link to bank accounts, or
          execute transactions on your behalf.
        </p>
      </section>

      <section>
        <h2>Your responsibilities</h2>
        <p>
          You&apos;re responsible for keeping your account credentials secure, for the accuracy
          of what you upload, and for only uploading statements you&apos;re authorized to use
          (your own, or ones you have explicit permission to process).
        </p>
      </section>

      <section>
        <h2>Not advice</h2>
        <p>
          Nothing in personalCFO — categorization, insights, chat answers, projections, or
          any other output — is financial, tax, or legal advice. AI-generated categorization
          and analysis can be inaccurate. Verify anything important against your actual
          statements before acting on it.
        </p>
      </section>

      <section>
        <h2>Limitation of liability</h2>
        <p>
          personalCFO is provided &quot;as is,&quot; without warranties of any kind. We are not
          liable for decisions made based on the app&apos;s output, or for any indirect,
          incidental, or consequential damages arising from its use.
        </p>
      </section>

      <section>
        <h2>Termination</h2>
        <p>
          You may stop using personalCFO and delete your account at any time. We may suspend
          or terminate accounts that violate these terms.
        </p>
      </section>

      <section>
        <h2>Governing law</h2>
        <p>These terms are governed by the laws of the United States, without regard to conflict-of-law principles.</p>
      </section>

      <section>
        <h2>Changes to these terms</h2>
        <p>
          We may update these terms as the product evolves. Material changes will be reflected
          by updating the date at the top of this page.
        </p>
      </section>

      <section>
        <h2>Contact</h2>
        <p>
          Questions about these terms:{" "}
          <a href="mailto:hello@personalcfo.app" className="text-blue-600 hover:underline">
            hello@personalcfo.app
          </a>
          .
        </p>
      </section>
    </LegalLayout>
  );
}
