## Depreciated

### Traefik SSL certs

The first time you start up the containers, the default is to use a staging server for SSL certs. Before running with production you will need to redirect the DNS of whatever domain name you want to use to the public IP of the server you're on. You set this public domain name in the `.env` file `EXTERNAL_API_DOMAIN` setting.

Then startup and look at the Traefik logs:

```bash
docker logs guid-slurp-traefik -f
```

It should look something like this:

```log
guid-slurp-traefik  | time="2023-05-30T12:54:21Z" level=info msg="Starting provider aggregator aggregator.ProviderAggregator"
guid-slurp-traefik  | time="2023-05-30T12:54:21Z" level=info msg="Starting provider *file.Provider"
guid-slurp-traefik  | time="2023-05-30T12:54:21Z" level=info msg="Starting provider *traefik.Provider"
guid-slurp-traefik  | time="2023-05-30T12:54:21Z" level=info msg="Starting provider *docker.Provider"
guid-slurp-traefik  | time="2023-05-30T12:54:21Z" level=info msg="Starting provider *acme.ChallengeTLSALPN"
guid-slurp-traefik  | time="2023-05-30T12:54:21Z" level=info msg="Starting provider *acme.Provider"
guid-slurp-traefik  | time="2023-05-30T12:54:21Z" level=info msg="Testing certificate renew..." ACME CA="https://acme-staging-v02.api.letsencrypt.org/directory" providerName=cloudflare-staging.acme
guid-slurp-traefik  | time="2023-05-30T12:54:21Z" level=info msg="Starting provider *acme.Provider"
guid-slurp-traefik  | time="2023-05-30T12:54:21Z" level=info msg="Testing certificate renew..." providerName=production.acme ACME CA="https://acme-v02.api.letsencrypt.org/directory"
guid-slurp-traefik  | time="2023-05-30T12:54:21Z" level=info msg="Starting provider *acme.Provider"
guid-slurp-traefik  | time="2023-05-30T12:54:21Z" level=info msg="Testing certificate renew..." providerName=staging.acme ACME CA="https://acme-staging-v02.api.letsencrypt.org/directory"
guid-slurp-traefik  | time="2023-05-30T12:54:21Z" level=info msg="Starting provider *acme.Provider"
guid-slurp-traefik  | time="2023-05-30T12:54:21Z" level=info msg="Testing certificate renew..." providerName=cloudflare-production.acme ACME CA="https://acme-v02.api.letsencrypt.org/directory"
```

Hopefully if you see something like that without any errors, you can move on and try to use a production server for your SSL certs.

A quick note about *Cloudflare*: if you're running behind Cloudflare, I think Cloudflare will accept staging certificates and then present real certificates to your users so you can leave it at this stage.

You should be able to view your site at https://your-domain-name.com/docs but you will get a certificate warning. If you push through and view the certificate you should see something like this:

```
Common Name (CN)	TRAEFIK DEFAULT CERT
Organization (O)	<Not Part Of Certificate>
Organizational Unit (OU)	<Not Part Of Certificate>
```

If you do have this, it means you can probably switch to the `production` SSL cert server. Edit the `.env` file:

```bash
# Run for the first time in 'staging' to avoid rate limits
# If everything is ok, change to 'production'
CERT_RESOLVER_STATUS='production'
```

And then restart everything:

```bash
docker compose up -d
```

And if everything goes according to plan you should be able to access the API Docs without any SSL warnings.