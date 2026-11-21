"""Corpus sintético (empresa fictícia Nimbus Cloud) usado na avaliação do RAG."""

DOCS: dict[str, str] = {
    "nimbus_planos.pdf": """Planos da Nimbus Cloud

Plano Starter: R$ 49 por mês, 1 projeto, 5 GB de armazenamento e suporte por e-mail em até 48 horas.

Plano Pro: R$ 199 por mês, 10 projetos, 100 GB de armazenamento e suporte por chat em até 4 horas.
O plano Pro inclui domínio personalizado e certificado SSL gratuito.

Plano Enterprise: preço sob consulta, projetos ilimitados, 1 TB de armazenamento, SLA de 99,95% de
disponibilidade e gerente de conta dedicado. O suporte funciona 24 horas por dia, 7 dias por semana.

Mudança de plano: o upgrade é imediato e o valor é calculado proporcionalmente aos dias restantes do ciclo.
O downgrade só vale a partir do próximo ciclo de cobrança.""",
    "nimbus_politica_reembolso.pdf": """Política de reembolso da Nimbus Cloud

O cliente pode solicitar reembolso integral em até 7 dias corridos após a primeira contratação,
conforme o direito de arrependimento do Código de Defesa do Consumidor.

Após 7 dias não há reembolso proporcional, mas o cliente pode cancelar a renovação a qualquer momento
pelo painel, em Configurações > Assinatura > Cancelar renovação.

O reembolso é feito no mesmo meio de pagamento usado na compra. Pagamentos no cartão de crédito
levam até 2 faturas para aparecer. Pagamentos via PIX são devolvidos em até 5 dias úteis.

Planos Enterprise seguem as condições do contrato assinado e não se aplicam a esta política.""",
    "nimbus_seguranca.pdf": """Segurança e privacidade na Nimbus Cloud

Todos os dados são criptografados em trânsito com TLS 1.3 e em repouso com AES-256.

Autenticação em dois fatores (2FA) está disponível em todos os planos e é obrigatória para contas
Enterprise. Para ativar, acesse Perfil > Segurança > Autenticação em dois fatores.

Os backups automáticos são diários e ficam retidos por 30 dias no plano Pro e por 90 dias no Enterprise.
O plano Starter não inclui backups automáticos.

Em caso de incidente de segurança, os clientes afetados são notificados em até 72 horas.
Os data centers ficam em São Paulo e em Virgínia, e o cliente escolhe a região ao criar o projeto.""",
}
