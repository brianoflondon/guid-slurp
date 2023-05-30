# guid-slurp
A Podcasting 2.0 GUID to RSS feed URL resolver with distributed databases


## Running with Docker (and scissors)

### Instructions

Get yourself a fresh new machine with Docker already installed and working.

```bash
git clone https://github.com/brianoflondon/guid-slurp.git
```

```bash
cd guid-slurp
````

Now you need to edit the `.env.sample` file and rename it `.env`.

Then run this:

```bash
docker compose up --build -d
```

If my calculations are correct, when you hit 88 MPH... oh, wait, no.

If everything is working properly, you can watch progress of startup with this:

```bash
docker compose logs -f | grep -v "guid-slurp-mongodb"
```

On first launch it will have to download the 1.4GB Database and then convert that into a smaller database.

Various steps will be shown in the logs. In addition the reverse proxy Traefik will start up and try to sort out SSL certs. The next version of these docs will hopefully have more info on this.

When all is settled down you should see something like this:

```log
guid-slurp-start    | 🟢Created collection of duplicatesGuidUrl
guid-slurp-start    | Finished database finalisation: 897.155 s
```

The API front end will then be available on `http://your_machine_ip:7777/docs` and on the internet depending on the settings you put in the .env file.
