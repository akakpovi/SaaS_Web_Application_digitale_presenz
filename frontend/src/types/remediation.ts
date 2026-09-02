export interface RemediationStep {
  order: number;
  description: string;
  codeSnippet?: string;
  language?: string;
}

export interface RemediationGuide {
  id: string;
  title: string;
  explanation: string;
  severity: "critical" | "warning" | "info";
  steps: RemediationStep[];
}

export const REMEDIATION_GUIDES: Record<string, RemediationGuide> = {
  spf_missing: {
    id: "spf_missing",
    title: "Enregistrement SPF manquant",
    explanation: "Votre domaine ne possède pas d'enregistrement SPF. Sans SPF, vos emails risquent d'être classés en spam ou rejetés par les serveurs destinataires.",
    severity: "critical",
    steps: [
      {
        order: 1,
        description: "Connectez-vous à la zone DNS de votre hébergeur (OVH, Cloudflare, etc.)."
      },
      {
        order: 2,
        description: "Ajoutez un enregistrement TXT avec la valeur SPF recommandée :",
        codeSnippet: "v=spf1 include:_spf.example.com ~all",
        language: "dns"
      },
      {
        order: 3,
        description: "Patientez le temps de la propagation DNS (quelques minutes à quelques heures) puis relancez un scan."
      }
    ]
  },
  ssl_expiring_soon: {
    id: "ssl_expiring_soon",
    title: "Certificat SSL expirant bientôt",
    explanation: "Votre certificat SSL expire dans moins de 30 jours. Renouvelez-le pour éviter les blocages de sécurité dans les navigateurs.",
    severity: "warning",
    steps: [
      {
        order: 1,
        description: "Renouvelez votre certificat via Certbot ou votre hébergeur :",
        codeSnippet: "sudo certbot renew --nginx",
        language: "bash"
      }
    ]
  },
  security_headers_missing: {
    id: "security_headers_missing",
    title: "En-têtes HTTP de sécurité manquants",
    explanation: "Votre serveur ne renvoie pas les en-têtes HTTP de sécurité recommandés (HSTS, CSP, X-Frame-Options).",
    severity: "critical",
    steps: [
      {
        order: 1,
        description: "Ajoutez les directives suivantes dans votre configuration Nginx :",
        codeSnippet: "add_header X-Content-Type-Options \"nosniff\" always;\nadd_header X-Frame-Options \"SAMEORIGIN\" always;\nadd_header Referrer-Policy \"strict-origin-when-cross-origin\" always;",
        language: "nginx"
      }
    ]
  }
};
