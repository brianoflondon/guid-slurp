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

Then run this if you wish to have a fully public API resolver (involving Traefik):

```bash
docker compose up --build -d
```

Alternatively for a local version only:
```bash
docker compose -f docker-compose-no-traefik.yaml up --build -d
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


### Logs and stuff

To see the containers you have running use this:

```bash
docker ps
```

You should see something like this:
```bash
CONTAINER ID   IMAGE                COMMAND                  CREATED         STATUS         PORTS                                                    NAMES
e5452edacfd9   guid-slurp-api       "gunicorn guid_slurp…"   4 minutes ago   Up 4 minutes   0.0.0.0:7777->80/tcp, :::7777->80/tcp                    guid-slurp-api
8d8d56b957e7   mongo:latest         "docker-entrypoint.s…"   4 minutes ago   Up 4 minutes   127.0.0.1:27017->27017/tcp, 127.0.1.1:27017->27017/tcp   guid-slurp-mongodb
36029929726a   guid-slurp-startup   "python guid_slurp/s…"   4 minutes ago   Up 4 minutes                                                            guid-slurp-start
```

To inspect logs from any of these use:

```bash
docker logs guid-slurp-startup -f
```

The startup script will run and then disappear. The others should remain running and will restart if the machine reboots.

I haven't written an automated way of updating the database every week... stay tuned!
