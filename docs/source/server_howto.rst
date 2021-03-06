=============
Server How To
=============

Setting Up a Koji Build System
==============================

The Koji components may **live** on separate resources as long as all resources
are able to communicate. This document will cover how to setup each service
individually, however, all services may **live** on the same resource.

Knowledge Prerequisites
=======================

* Basic understanding of SSL and authentication via certificates and/or
  Kerberos credentials
* Basic knowledge about creating a database in PostgreSQL and importing a schema
* Working with psql
* Basic knowledge about Apache configuration
* Basic knowledge about `dnf`_/`yum`_/`createrepo`_/`mock`_ - else you'll not
  be able to debug problems!
* Basic knowledge about using command line
* Basic knowledge about RPM building
* Simple usage of the Koji client
* For an overview of yum, mock, Koji (and all its subcomponents), mash, and how
  they all work together, see the excellent slides put together by `Steve
  Traylen at CERN <http://indico.cern.ch/event/55091>`_.

Package Prerequisites
=====================

On the server (koji-hub/koji-web)
---------------------------------
* httpd
* mod_ssl
* postgresql-server
* mod_wsgi

On the builder (koji-builder)
-----------------------------
* mock
* setarch (for some archs you'll require a patched version)
* rpm-build
* createrepo

A note on filesystem space
==========================
Koji will consume copious amounts of disk space under the primary KojiDir
directory (as set in the kojihub.conf file - defaults to ``/mnt/koji``).
However, as koji makes use of mock on the backend to actually create build
roots and perform the builds in those build roots, it might come to a surprise
to users that a running koji server will consume large amounts of disk space
under ``/var/lib/mock`` and ``/var/cache/mock`` as well. Users should either
plan the disk and filesystem allocations for this, or plan to modify the
default mock build directory in the kojid.conf file. If you change the
location, ensure that the new directories are owned by the group "mock" and
have 02755 permission.

Koji Authentication Selection
=============================
Koji primarily supports Kerberos and SSL Certificate authentication. For basic
koji command line access, plain user/pass combinations are possible.  However,
kojiweb does **not** support plain user/pass authentication and once either
Kerberos or SSL Certificate authentication is enabled for kojiweb, the plain
user/pass method will stop working entirely.  For this reason we encourage
skipping the plain user/pass method altogether and properly configuring either
Kerberos or SSL Certification authentication from the start.

The decision on how to authenticate users will affect all other actions you
take in setting up koji. For this reason it is a decision best made up front.

For Kerberos authentication
    a working Kerberos environment (the user is assumed to either already have
    this or know how to set it up themselves, instructions for it are not
    included here) and the Kerberos credentials of the initial admin user will
    be necessary to bootstrap the user database.

For SSL authentication
    SSL certificates for the xmlrpc server, for the various koji components,
    and one for the admin user will need to be setup (the user need not know
    how to create certificate chains already, we include the instructions for
    this below).

Setting up SSL Certificates for authentication
----------------------------------------------

Certificate generation
^^^^^^^^^^^^^^^^^^^^^^
Create the ``/etc/pki/koji`` directory and copy-and-paste the ssl.cnf listed
here, and save it in the new directory. This configuration file is used along
with the ``openssl`` command to generate the SSL certificates for the various
koji components.

``ssl.cnf``

::

    <pre>
    HOME                    = .
    RANDFILE                = .rand

    [ca] 
    default_ca              = ca_default

    [ca_default] 
    dir                     = .
    certs                   = $dir/certs
    crl_dir                 = $dir/crl
    database                = $dir/index.txt
    new_certs_dir           = $dir/newcerts
    certificate             = $dir/%s_ca_cert.pem
    private_key             = $dir/private/%s_ca_key.pem
    serial                  = $dir/serial
    crl                     = $dir/crl.pem
    x509_extensions         = usr_cert
    name_opt                = ca_default
    cert_opt                = ca_default
    default_days            = 3650
    default_crl_days        = 30
    default_md              = sha256
    preserve                = no
    policy                  = policy_match

    [policy_match] 
    countryName             = match
    stateOrProvinceName     = match
    organizationName        = match
    organizationalUnitName  = optional
    commonName              = supplied
    emailAddress            = optional

    [req] 
    default_bits            = 1024
    default_keyfile         = privkey.pem
    distinguished_name      = req_distinguished_name
    attributes              = req_attributes
    x509_extensions         = v3_ca # The extentions to add to the self signed cert
    string_mask             = MASK:0x2002

    [req_distinguished_name] 
    countryName                     = Country Name (2 letter code)
    countryName_default             = AT
    countryName_min                 = 2
    countryName_max                 = 2
    stateOrProvinceName             = State or Province Name (full name)
    stateOrProvinceName_default     = Vienna
    localityName                    = Locality Name (eg, city)
    localityName_default            = Vienna
    0.organizationName              = Organization Name (eg, company)
    0.organizationName_default      = My company
    organizationalUnitName          = Organizational Unit Name (eg, section)
    commonName                      = Common Name (eg, your name or your server\'s hostname)
    commonName_max                  = 64
    emailAddress                    = Email Address
    emailAddress_max                = 64

    [req_attributes] 
    challengePassword               = A challenge password
    challengePassword_min           = 4
    challengePassword_max           = 20
    unstructuredName                = An optional company name

    [usr_cert] 
    basicConstraints                = CA:FALSE
    nsComment                       = "OpenSSL Generated Certificate"
    subjectKeyIdentifier            = hash
    authorityKeyIdentifier          = keyid,issuer:always

    [v3_ca] 
    subjectKeyIdentifier            = hash
    authorityKeyIdentifier          = keyid:always,issuer:always
    basicConstraints                = CA:true

Although it is not required, it is recommended that you edit the default values
in the ``[req_distinguished_name]`` section of the configuration to match the
information for your own server. This will allow you to accept most of the
default values when generating certificates later. The other sections can be
left unedited.

Generate CA
^^^^^^^^^^^

The CA is the Certificate Authority.  It's the key/cert pair used to sign all
the other certificate requests.  When configuring the various koji components,
both the client CA and the server CA will be a copy of the CA generated here.
The CA certificate will be placed in the ``/etc/pki/koji`` directory and the
certificates for the other components will be placed in the
``/etc/pki/koji/certs`` directory. The ``index.txt`` file which is created is
a database of the certificates generated and can be used to view the
information for any of the certificates simply by viewing the contents of
``index.txt``.

::

    cd /etc/pki/koji/
    mkdir {certs,private,confs}
    touch index.txt
    echo 01 > serial
    openssl genrsa -out private/koji_ca_cert.key 2048
    openssl req -config ssl.cnf -new -x509 -days 3650 -key private/koji_ca_cert.key \
    -out koji_ca_cert.crt -extensions v3_ca

The last command above will ask you to confirm a number of items about the
certificate you are generating. Presumably you already edited the defaults for
the country, state/province, locale, and organization in the ``ssl.cnf`` file
and you only needed to hit enter. It's the organizational unit and the common
name that we will be changing in the various certs we create. For the CA
itself, these fields don't have a hard requirement. One suggestion for this
certificate is to use the FQDN of the server.

If you are trying to automate this process via a configuration management
tool, you can create the cert in one command with a line like this:

::

    openssl req -config ssl.cnf -new -x509 \
    -subj "/C=US/ST=Oregon/L=Portland/O=IT/CN=koji.example.com" \
    -days 3650 -key private/koji_ca_cert.key -out koji_ca_cert.crt -extensions v3_ca

Generate the koji component certificates and the admin certificate
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Each koji component needs its own certificate to identify it. Two of the
certificates (kojihub and kojiweb) are used as server side certificates that
authenticate the server to the client. For this reason, you want the common
name on both of those certs to be the fully qualified domain name of the web
server they are running on so that clients don't complain about the common
name and the server not being the same. You can set the OU for these two
certificates to be kojihub and kojiweb for identification purposes.

For the other certificates (kojira, kojid, the initial admin account, and all
user certificates), the cert is used to authenticate the client to the server.
The common name for these certs should be set to the login name for that
specific component. For example the common name for the kojira cert should be
set to kojira so that it matches the username. The reason for this is that the
common name of the cert will be matched to the corresponding user name in the
koji database. If there is not a username in the database which matches the CN
of the cert the client will not be authenticated and access will be denied.

When you later use ``koji add-host`` to add a build machine into the koji
database, it creates a user account for that host even though the user account
doesn't appear in the user list.  The user account created must match the
common name of the certificate which that component uses to authenticate with
the server. When creating the kojiweb certificate, you'll want to remember
exactly what values you enter for each field as you'll have to regurgitate
those into the /etc/koji-hub/hub.conf file as the ProxyDNs entry.

When you need to create multiple certificates it may be convenient to create a
loop or a script like the on listed below and run the script to create the
certificates. You can simply adjust the number of kojibuilders and the name of
the admin account as you see fit. For much of this guide, the admin account is
called ``kojiadmin``.

::

    #!/bin/bash
    # if you change your certificate authority name to something else you will
    # need to change the caname value to reflect the change.
    caname=koji

    # user is equal to parameter one or the first argument when you actually
    # run the script
    user=$1

    openssl genrsa -out private/${user}.key 2048
    cat ssl.cnf | sed 's/insert_hostname/'${user}'/'> ssl2.cnf
    openssl req -config ssl2.cnf -new -nodes -out certs/${user}.csr -key private/${user}.key
    openssl ca -config ssl2.cnf -keyfile private/${caname}_ca_cert.key -cert ${caname}_ca_cert.crt \
        -out certs/${user}.crt -outdir certs -infiles certs/${user}.csr
    cat certs/${user}.crt private/${user}.key > ${user}.pem
    mv ssl2.cnf confs/${user}-ssl.cnf

Generate a PKCS12 user certificate (for web browser)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
This is only required for user certificates.

::

    openssl pkcs12 -export -inkey private/${user}.key -in certs/${user}.crt \
        -CAfile ${caname}_ca_cert.crt -out certs/${user}_browser_cert.p12

When generating certs for a user, the user will need the ``${user}.pem``, the
``${caname}_ca_cert.crt``, and the ``${user}_browser_cert.p12`` files which
were generated above.  The ${user}.pem file would normally be installed as
``~/.fedora.cert``, the ``${caname}_ca_cert.crt`` file would be installed as
both ``~/.fedora-upload-ca.cert`` and ``~/.fedora-server-ca.cert``, and the
user would import the ``${user}_brower_cert.p12`` into their web browser as a
personal certificate.

Copy certificates into ~/.koji for kojiadmin
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You're going to want to be able to send admin commands to the kojihub. In order
to do so, you'll need to use the newly created certificates to authenticate
with the hub. Create the kojiadmin user then copy the certificates for the koji
CA and the kojiadmin user to ``~/.koji``:

::

    kojiadmin@localhost$ mkdir ~/.koji
    kojiadmin@localhost$ cp /etc/pki/koji/kojiadmin.pem ~/.koji/client.crt   # NOTE: It is IMPORTANT you use the PEM and NOT the CRT
    kojiadmin@localhost$ cp /etc/pki/koji/koji_ca_cert.crt ~/.koji/clientca.crt
    kojiadmin@localhost$ cp /etc/pki/koji/koji_ca_cert.crt ~/.koji/serverca.crt

.. note::
    See /etc/koji.conf for the current system wide koji client configuration.
    Copy /etc/koji.conf to ~/.koji/config if you wish to change the config on a
    per user basis.

Setting up Kerberos for authentication
--------------------------------------

The initial configuration of a kerberos service is outside the scope of this
document, however there are a few specific things required by koji.

DNS
^^^

The koji builders (kojid) use DNS to find the kerberos servers for any given
realm.

::

    _kerberos._udp    IN SRV  10 100 88 kerberos.EXAMPLE.COM.

The trailing dot denotes DNS root and is needed if FQDN is used.


Principals and Keytabs
^^^^^^^^^^^^^^^^^^^^^^

It should be noted that in general you will need to use the fully qualified
domain name of the hosts when generating the keytabs for services.

You will need the following principals extracted to a keytab for a fully
kerberized configuration, the requirement for a host key for the koji-hub is
currently hard coded into the koji client.

``host/kojihub@EXAMPLE.COM``
    Used by the koji-hub server when communicating with the koji client

``HTTP/kojiweb@EXAMPLE.COM``
    Used by the koji-web server when performing a negotiated Kerberos
    authentication with a web browser. This is a service principal for
    Apache's mod_auth_kerb.

``koji/kojiweb@EXAMPLE.COM``
    Used by the koji-web server during communications with the koji-hub. This
    is a user principal that will authenticate koji-web to Kerberos as
    "koji/kojiweb@EXAMPLE.COM". Koji-web will proxy the mod_auth_kerb user
    information to koji-hub (the <code>ProxyPrincipals</code> koji-hub config
    option).

``koji/kojira@EXAMPLE.COM``
    Used by the kojira server during communications with the koji-hub

``compile/builder1@EXAMPLE.COM``
    Used on builder1 to communicate with the koji-hub

PostgreSQL Server
=================

Once the authentication scheme has been setup your will need to install and
configure a PostgreSQL server and prime the database which will be used to hold
the koji users.

Configuration Files
-------------------

* ``/var/lib/pgsql/data/pg_hba.conf``
* ``/var/lib/pgsql/data/postgresql.conf``

Install PostgreSQL
------------------

In Fedora 22 and Later versions use `dnf`_:

::

    # dnf install postgresql-server

Or `yum`_ in Fedora 21 and earlier versions: 

::

    # yum install postgresql-server

Initialize PostgreSQL DB:
-------------------------

The following commands will initialize PostgreSQL and will start the database service

::

    root@localhost$ su - postgres -c "PGDATA=/var/lib/pgsql/data initdb"
    root@localhost$ systemctl enable postgresql
    root@localhost$ systemctl start postgresql

Setup User Accounts:
--------------------

The following commands will setup the ``koji`` account and assign it a password

::

    root@localhost$ useradd koji
    root@localhost$ passwd koji

Setup PostgreSQL and populate schema:
-------------------------------------

The following commands will:

* create the koji user within PostgreSQL
* create the koji database within PostgreSQL
* set a password for the koji user
* create the koji schema using the provided
  ``/usr/share/doc/koji*/docs/schema.sql`` file

::

    root@localhost$ su - postgres
    postgres@localhost$ createuser --no-superuser --no-createrole --no-createdb koji
    postgres@localhost$ createdb -O koji koji
    postgres@localhost$ psql -c "alter user koji with encrypted password 'mypassword';"
    postgres@localhost$ logout
    root@localhost$ su - koji
    koji@localhost$ psql koji koji < /usr/share/doc/koji*/docs/schema.sql
    koji@localhost$ exit

.. note::
    When issuing the command to import the psql schema into the new database it
    is important to ensure that the directory path
    /usr/share/doc/koji*/docs/schema.sql remains intact and is not resolved to
    a specific version of koji. In test it was discovered that when the path is
    resolved to a specific version of koji then not all of the tables were
    created correctly.

.. note::
    When issuing the command to import the psql schema into the new database it
    is important to ensure that you are logged in as the koji database owner.
    This will ensure all objects are owned by the koji database user. Upgrades
    may be difficult if this was not done correctly.

Authorize Koji-web and Koji-hub resources
-----------------------------------------

.. note::
    In this example, Koji-web and Koji-hub are running on localhost.

``/var/lib/pgsql/data/pg_hba.conf``
    These settings need to be valid and inline with other services
    configurations. Please note, the first matching auth line is used so this
    line must be above any other potential matches. Add:

    ::

        #TYPE   DATABASE    USER    CIDR-ADDRESS      METHOD
        host    koji        koji    127.0.0.1/32      trust
        host    koji        koji     ::1/128          trust

    It may also be necessary to add an entry for your machine's external IP
    address:

    ::

        host    koji        koji    $IP_ADDRESS/32    trust

    You can also use UNIX socket access. The DBHost variable must be unset to
    use this method. Add:

    ::

        local   koji        apache                            trust
        local   koji        koji                              trust

    .. note::
        To enforce password based logins to the database, change <tt>trust</tt> to <tt>md5</tt>.

    ::

        #TYPE   DATABASE    USER    CIDR-ADDRESS      METHOD
        host    koji        koji    127.0.0.1/32      md5
        host    koji        koji     ::1/128          md5
        host    koji        koji    $IP_ADDRESS/32    md5

    Make auth changes live:
    You must reload the PostgreSQL configuration for these changes to become active.

    ::

        root@localhost$ systemctl reload postgresql

Bootstrapping the initial koji admin user into the PostgreSQL database
----------------------------------------------------------------------

The initial admin user must be manually added to the user database using sql
commands.  Once added and given admin privilege, you may add additional users
and change privileges of those users via the koji command line tool's
administrative commands.

However, if you decided to use the simple user/pass method of authentication,
then any password setting/changing must be done manually via sql commands as
there is no password manipulation support exposed through the koji tools.

The sql commands you need to use vary by authentication mechanism.

Set User/Password Authentication
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

    root@localhost$ su - koji
    koji@localhost$ psql
    koji=> insert into users (name, password, status, usertype) values ('admin-user-name', 'admin-password-in-plain-text', 0, 0);

Kerberos authentication
^^^^^^^^^^^^^^^^^^^^^^^

The process is very similar to user/pass except you would replace the first
insert above with this:

::

    root@localhost$ su - koji
    koji@localhost$ psql
    koji=> insert into users (name, krb_principal, status, usertype) values ('admin-user-name', 'admin@EXAMPLE.COM', 0, 0);

SSL Certificate authentication
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There is no need for either a password or a Kerberos principal, so this will
suffice:

::

    root@localhost$ su - koji
    koji@localhost$ psql
    koji=> insert into users (name, status, usertype) values ('admin-user-name', 0, 0);

Give yourself admin permissions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following command will give the user admin permissions. In order to do
this you will need to know the ID of the user.

::

    koji=> insert into user_perms (user_id, perm_id, creator_id) values (<id of user inserted above>, 1, <id of user inserted above>);

.. note::
    If you do not know the ID of the admin user, you can get the ID by running the query:

::

    koji=> select * from users;

You can't actually log in and perform any actions until kojihub is up and
running in your web server.  In order to get to that point you still need to
complete the authentication setup and the kojihub configuration. If you wish
to access koji via a web browser, you will also need to get kojiweb up and
running.

Set Database To Listen On All Addresses
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The koji-hub service will attempt to connect to the database server in the
manner you configure.  If you use the system hostname, then the database will
need to be avalible on that address.  To configure this please perform the
following:

#.  Edit /var/lib/pgsql/data/postgresql.conf
#.  Set listen_address

    ::

        listen_addresses = '*'
#.  Reload the postgresql service

    ::
        systemctl restart postgresql

Koji Hub
========

.. note::
    Koji 1.7 and greater uses mod_wsgi.  Any mod_python configurations will
    need to be migrated.

Koji-hub is the center of all Koji operations. It is an XML-RPC server running
under mod_wsgi in the Apache httpd. koji-hub is passive in that it only
receives XML-RPC calls and relies upon the build daemons and other components
to initiate communication. Koji-hub is the only component that has direct
access to the database and is one of the two components that have write access
to the file system.

Configuration Files
-------------------

* ``/etc/koji-hub/hub.conf``
* ``/etc/httpd/conf/httpd.conf``
* ``/etc/httpd/conf.d/kojihub.conf``
* ``/etc/httpd/conf.d/ssl.conf`` (when using ssl auth)

Install koji-hub
----------------

In Fedora 22 and later versions use `dnf`_: 

::

    # dnf install koji-hub httpd mod_ssl

Or with `yum`_ in Fedora 21 and earlier versions:

::

    # yum install koji-hub httpd mod_ssl

Required Configuration
----------------------

/etc/httpd/conf/httpd.conf
^^^^^^^^^^^^^^^^^^^^^^^^^^

The apache web server has two places that it sets maximum requests a server
will handle before the server restarts. The xmlrpc interface in kojihub is a
python application, and processes can sometimes grow outrageously large when it
doesn't reap memory often enough. As a result, it is strongly recommended that
you set both instances of MaxRequestsPerChild in httpd.conf to something
reasonable in order to prevent the server from becoming overloaded and crashing
(at 100 the httpd processes will grow to about 75MB resident set size before
respawning).

::

    <IfModule prefork.c>
    ...
    MaxRequestsPerChild  100
    </IfModule>
    <IfModule worker.c>
    ...
    MaxRequestsPerChild  100
    </IfModule>

/etc/httpd/conf.d/kojihub.conf
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The koji-hub package provides this configuration file. You will need to modify
it based on your authentication type. Instructions are contained within the
file and should be simple to follow.

/etc/httpd/conf.d/ssl.conf
^^^^^^^^^^^^^^^^^^^^^^^^^^

If using SSL you will also need to add the needed SSL options for apache. These
options should point to where the certificates are located on the hub.

::

    SSLCertificateFile /etc/pki/koji/certs/kojihub.crt
    SSLCertificateKeyFile /etc/pki/koji/certs/kojihub.key
    SSLCertificateChainFile /etc/pki/koji/koji_ca_cert.crt
    SSLCACertificateFile /etc/pki/koji/koji_ca_cert.crt
    SSLVerifyClient require
    SSLVerifyDepth  10

/etc/koji-hub/hub.conf
^^^^^^^^^^^^^^^^^^^^^^

This file contains the configuration information for the hub. You will need to
edit this configuration to point Koji Hub to the database you are using and to
setup Koji Hub to utilize the authentication scheme you selected in the
beginning.

::

    DBName = koji
    DBUser = koji
    DBPass = mypassword
    DBHost = db.example.com
    KojiDir = /mnt/koji
    LoginCreatesUser = On
    KojiWebURL = http://kojiweb.example.com/koji

If kojihub is running on the same server as the koji db, then DBHost should be
set to 127.0.0.1

Authentication Configuration
----------------------------

/etc/koji-hub/hub.conf
^^^^^^^^^^^^^^^^^^^^^^

If using Kerberos, these settings need to be valid and inline with other
services configurations.

::

    AuthPrincipal host/kojihub@EXAMPLE.COM
    AuthKeytab /etc/koji.keytab
    ProxyPrincipals koji/kojiweb@EXAMPLE.COM
    HostPrincipalFormat compile/%s@EXAMPLE.COM

If using SSL auth, these settings need to be valid and inline with other
services configurations for kojiweb to allow logins.

ProxyDNs should be set to the DN of the kojiweb certificate.  The exact format
depends on your mod_ssl version.

For mod_ssl < 2.3.11 use:

::

    DNUsernameComponent = CN
    ProxyDNs = /C=US/ST=Massachusetts/O=Example Org/OU=kojiweb/CN=example/emailAddress=example@example.com

However, for mod_ssl >= 2.3.11 use:

::

    DNUsernameComponent = CN
    ProxyDNs = CN=example.com,OU=kojiweb,O=Example Org,ST=Massachusetts,C=US

.. note::
    More details on this format change, including handling of special
    characters, can be found in the `Apache mod_ssl documentation`_.  See
    LegacyDNStringFormat there.

Koji filesystem skeleton
^^^^^^^^^^^^^^^^^^^^^^^^

Above in the ``kojihub.conf`` file we set KojiDir to ``/mnt/koji``.  For
certain reasons, if you change this, you should make a symlink from
``/mnt/koji`` to the new location (note: this is a bug and should be fixed
eventually).  However, before other parts of koji will operate properly, we
need to create a skeleton filesystem structure for koji as well as make the
file area owned by apache so that the xmlrpc interface can write to it as
needed.

::

    cd /mnt
    mkdir koji
    cd koji
    mkdir {packages,repos,work,scratch}
    chown apache.apache *

SELinux Configuration
^^^^^^^^^^^^^^^^^^^^^

If running in Enforcing mode
    * you will need to allow apache to connect to the postgreSQL server
    * you will need to allow apache to write some files to disk

Even if you are not currently running in Enforcing mode, it is still
recommended to configure the SELinux settings so that there are no future
issues with SELinux if Enforcing mode is enabled later on.

::

    root@localhost$ setsebool -P httpd_can_network_connect_db=1 allow_httpd_anon_write=1
    root@localhost$ chcon -R -t public_content_rw_t /mnt/koji/*

If you've placed ``/mnt/koji`` on an NFS share you may also need to set
``httpd_use_nfs``.

Check Your Configuration
^^^^^^^^^^^^^^^^^^^^^^^^

At this point, you can now restart apache and you should have at least minimal
operation.  The admin user should be able to connect via the command line
client, add new users, etc.  It's possible at this time to undertake initial
administrative steps such as adding users and hosts to the koji database.

So we will need a working client to test with.

Koji cli - The standard client
==============================

The koji cli is the standard client. It can perform most tasks and is essential
to the successful use of any koji environment.

Ensure that your client is configured to work with your server. The system-wide
koji client configuration file is ``/etc/koji.conf``, and the user-specific one
is in ``~/.koji/config``. You may also use the ``-c`` option when using the
Koji client to specify an alternative configuration file.

If you are using SSL for authentication, you will need to edit the Koji client
configuration to tell it which URLs to use for the various Koji components and
where their SSL certificates can be found.

For a simple test, all we need is the ``server`` and authentication sections.

::

    [koji]

    ;url of XMLRPC server
    server = http://koji-hub.example.com/kojihub

    ;url of web interface
    weburl = http://koji-web.example.com/koji

    ;url of package download site
    topurl = http://koji-filesystem.example.com/kojifiles

    ;path to the koji top directory
    topdir = /mnt/koji

    ; configuration for Kerberos authentication

    ;the service name of the principal being used by the hub
    ;krbservice = host

    ; configuration for SSL athentication

    ;client certificate
    cert = ~/.koji/client.crt

    ;certificate of the CA that issued the client certificate
    ca = ~/.koji/clientca.crt

    ;certificate of the CA that issued the HTTP server certificate
    serverca = ~/.koji/serverca.crt

The following command will test your login to the hub:

::

    root@localhost$ koji moshimoshi

Koji Web - Interface for the Masses
===================================

.. note::
    Koji 1.7 and greater uses mod_wsgi.  Any mod_python configurations will
    need to be migrated.

Koji-web is a set of scripts that run in mod_wsgi and use the Cheetah
templating engine to provide an web interface to Koji. koji-web exposes a lot
of information and also provides a means for certain operations, such as
cancelling builds.

Configuration Files
-------------------

* ``/etc/httpd/conf.d/kojiweb.conf``
* ``/etc/httpd/conf.d/ssl.conf``
* ``/etc/kojiweb/web.conf``

Install Koji-Web
----------------

For Fedora 22 and later versions use `dnf`_:

::

    # dnf install koji-web mod_ssl

Or with `yum`_ for Fedora 21 and earlier versions:

::

    # yum install koji-web mod_ssl

Required Configuration
----------------------

/etc/httpd/conf.d/kojiweb.conf
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The koji-web package provides this configuration file. You will need to modify
it based on your authentication type. Instructions are contained within the
file and should be simple to follow.

.. note::
    RHEL 5's mod_python publisher does not support non-basic auth, so Kerberos
    authentication does not currently work in EPEL 5's Koji-web. See
    `BZ #682319 <https://bugzilla.redhat.com/682319>`_.

/etc/httpd/conf.d/ssl.conf
^^^^^^^^^^^^^^^^^^^^^^^^^^

If you are using SSL you will need to add the needed SSL options for apache.

::

    SSLVerifyClient require
    SSLVerifyDepth  10

/etc/kojiweb/web.conf
^^^^^^^^^^^^^^^^^^^^^

You will need to edit the kojiweb configuration file to tell kojiweb which URLs
it should use to access the hub, the koji packages and its own web interface.
You will also need to tell kojiweb where it can find the SSL certificates for
each of these components. If you are using SSL authentication, the "WebCert"
line below must contain both the public **and** private key. You will also want
to change the last line in the example below to a unique password.

::

    [web]
    SiteName = koji
    # KojiTheme = 

    # Necessary urls
    KojiHubURL = https://koji-hub.example.com/kojihub
    KojiFilesURL = http://koji-filesystem.example.com/kojifiles

    ## Kerberos authentication options
    ; WebPrincipal = koji/web@EXAMPLE.COM
    ; WebKeytab = /etc/httpd.keytab
    ; WebCCache = /var/tmp/kojiweb.ccache

    ## SSL authentication options
    ; WebCert = /etc/pki/koji/koji-web.pem
    ; ClientCA = /etc/pki/koji/ca_cert.crt
    ; KojiHubCA = /etc/pki/koji/ca_cert.crt

    LoginTimeout = 72

    # This must be set before deployment
    #Secret = CHANGE_ME

    LibPath = /usr/share/koji-web/lib

Filesystem Configuration
------------------------

You'll need to make ``/mnt/koji/`` web-accessible, either here, on the hub, or
on another web server altogether.

This URL will go into various clients such as:
* ``/etc/kojiweb/web.conf`` as KojiFilesURL
* ``/etc/kojid/kojid.conf`` as topurl
* ``/etc/koji.conf`` as topurl

::

    Alias /kojifiles/ /mnt/koji/
    <Directory "/mnt/koji/">
        Options Indexes
        AllowOverride None
        # Apache < 2.4
        #   Order allow,deny
        #   Allow from all
        # Apache >= 2.4
        Require all granted
    </Directory>

Wherever you configure this, please go back and set it correctly in
``/etc/kojiweb/web.conf`` now.

Web interface now operational
-----------------------------

At this point you should be able to point your web browser at the kojiweb URL
and be presented with the koji interface.  Many operations should work in read
only mode at this point, and any configured users should be able to log in.

Koji Daemon - Builder
=====================

Kojid is the build daemon that runs on each of the build machines. Its primary
responsibility is polling for incoming build requests and handling them
accordingly. Koji also has support for tasks other than building such as
creating livecd images or raw disk images, and kojid is responsible for
handling these tasks as well. The kojid service uses mock for creating pristine
build environments and creates a fresh one for every build, ensuring that
artifacts of build processes cannot contaminate each other. All of kojid is
written in Python and communicates with koji-hub via XML-RPC.

Configuration Files
-------------------

* ``/etc/kojid/kojid.conf`` - Koji Daemon Configuration
* ``/etc/sysconfig/kojid`` - Koji Daemon Switches

Install kojid
-------------

For Fedora 22 and later versions use `dnf`_:

::

    # dnf install koji-builder

Or with `yum`_ in Fedora 21 and earlier versions:

::

    # yum install koji-builder

Required Configuration
----------------------

Add the host entry for the koji builder to the database
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You will now need to add the koji builder to the database so that they can be
utilized by kojij hub. Make sure you do this before you start kojid for the
first time, or you'll need to manually remove entries from the sessions and
users table before it can be run successfully.

::

    kojiadmin@localhost$ koji add-host kojibuilder1.example.com i386 x86_64

The first argument used after the ``add-host`` command should the hostname of
the builder. The second argument is used to specify the architecture which the
builder uses.


/etc/kojid/kojid.conf
^^^^^^^^^^^^^^^^^^^^^

The configuration file for each koji builder must be edited so that the line
below points to the URL for the koji hub. The user tag must also be edited to
point to the username used to add the koji builder.

::

    ; The URL for the xmlrpc server
    server=http://hub.example.com/kojihub

    ; the username has to be the same as what you used with add-host
    ; in this example follow as below
    user = kojibuilder1.example.com

The koji filesystem may also be needed over http.  Set this as it was
configured about.

::

    # The URL for the file access
    topurl=http://koji-filesystem.example.com/kojifiles

This item may be changed, but may not be the same as KojiDir on the
``kojihub.conf`` file (although it can be something under KojiDir, just not
the same as KojiDir)

::

    ; The directory root for temporary storage
    workdir=/tmp/koji

The root of the koji build directory (ie, ``/mnt/koji``) must be mounted on the
builder. A Read-Only NFS mount is the easiest way to handle this.

::

    # The directory root where work data can be found from the koji hub
    topdir=/mnt/koji

Authentication Configuration (SSL certificates)
-----------------------------------------------

/etc/kojid/kojid.conf
^^^^^^^^^^^^^^^^^^^^^

If you are using SSL, these settings need to be edited to point to the
certificates you generated at the beginning of the setup process.

::

    ;client certificate
    ; This should reference the builder certificate we created on the kojihub CA, for kojibuilder1.example.com
    ; ALSO NOTE: This is the PEM file, NOT the crt
    cert = /etc/kojid/kojid.pem

    ;certificate of the CA that issued the client certificate
    ca = /etc/kojid/koji_ca_cert.crt

    ;certificate of the CA that issued the HTTP server certificate
    serverca = /etc/kojid/koji_ca_cert.crt

It is important to note that if your builders are hosted on seperate machines
from koji hub and koji web, you will need to scp the certificates mentioned in
the above configuration file from the ``/etc/kojid/`` directory on koji hub to
the ``/etc/koji/`` directory on the local machine so that the builder can be
authenticated.

Authentication Configuration (Kerberos)
---------------------------------------

/etc/kojid/kojid.conf
^^^^^^^^^^^^^^^^^^^^^

If using Kerberos, these settings need to be valid and inline with other
services configurations.

::

    ; the username has to be the same as what you used with add-host
    ;user =

    host_principal_format=compile/%s@EXAMPLE.COM

By default it will look for the Kerberos keytab in ``/etc/kojid/kojid.keytab``

.. note::
    Kojid will not attempt kerberos authentication to the koji-hub unless the
    username field is commented out

Optional Configuration SourceCodeManagement
-------------------------------------------

/etc/kojid/kojid.conf
^^^^^^^^^^^^^^^^^^^^^

The pattern is as follows:
    hostname:/path/match:checkout /common?, hostname2:/path/match:checkout /common?

``checkout /common? is 'true' unless set to false``

::

    allowed_scms=scm-server.example.com:/repo/base/repos*/:false

Once the code is checked out kojid will run the following:

::

    make sources
    mv *.spec <rpmbuild>/SPECS
    mv * <rpmbuild>/SOURCES
    rpmbuild -bs <rpmbuild>/SPECS/*.spec

Add the host to the createrepo channel
--------------------------------------

Channels are a way to control which builders process which tasks.  By default
hosts are added to the ''default'' channel.  At least some build hosts also
needs to be added to the ''createrepo'' channel so there will be someone to
process repo creation tasks initiated by kojira.

::

    kojiadmin@localhost$ koji add-host-to-channel kojibuilder1.example.com createrepo

A note on capacity
------------------

The default capacity of a host added to the host database is 2. This means that
once the load average on that machine exceeds 2, kojid will not accept any
additional tasks. This is separate from the maxjobs item in the configuration
file. Before kojid will accept a job, it must pass both the test to ensure the
load average is below capacity and that the current number of jobs it is
already processing is less than maxjobs. However, in today's modern age of quad
core and higher CPUs, a load average of 2 is generally insufficient to fully
utilize hardware.

::

    koji edit-host --capacity=16 kojibuilder1.example.com

The koji-web interface also offers the ability to edit this value to admin
accounts.

Start Kojid
-----------

Once the builder has been added to the database you must start kojid

::

    root@localhost$ service kojid start

Check ``/var/log/kojid.log`` to verify that kojid has started successfully. If
the log does not show any errors then the koji builder should be up and ready.
You can check this by pointing your web browser to the web interface and
clicking on the hosts tab. This will show you a list of builders in the
database and the status of each builder.

Kojira - Dnd|Yum repository creation and maintenance
====================================================

Configuration Files
-------------------

* ``/etc/kojira/kojira.conf`` - Kojira Daemon Configuration
* ``/etc/sysconfig/kojira`` - Kojira Daemon Switches

Install kojira
---------------
For Fedora 22 and later versions use `dnf`_:

::

    # dnf install koji-utils

Or with `yum`_ in Fedora 21 and earlier versions:

::

    # yum install koji-utils

Required Configuration
----------------------

Add the user entry for the kojira user
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The kojira user requires the ``repo`` permission to function.

::

    kojiadmin@localhost$ koji add-user kojira
    kojiadmin@localhost$ koji grant-permission repo kojira

``/etc/kojira/kojira.conf``
    This needs to point at your koji-hub.

    ::

        ; The URL for the xmlrpc server
        server=http://koji-hub.example.com/kojihub


Additional Notes
^^^^^^^^^^^^^^^^
* Kojira needs read-write access to ``/mnt/koji``.
* There should only be one instance of kojira running at any given time.
* It is not recommended that kojira run on the builders, as builders only
  should require read-only access to ``/mnt/koji``.
* Kojira may need to be restarted when new tags are added in order to detect
  those tags correctly.

Authentication Configuration
----------------------------

/etc/kojira/kojira.conf
^^^^^^^^^^^^^^^^^^^^^^^

**If using SSL,** these settings need to be valid.

::

    ;client certificate
    ; This should reference the kojira certificate we created above
    cert = /etc/pki/koji/kojira.pem

    ;certificate of the CA that issued the client certificate
    ca = /etc/pki/koji/koji_ca_cert.crt

    ;certificate of the CA that issued the HTTP server certificate
    serverca = /etc/pki/koji/koji_ca_cert.crt

**If using Kerberos,** these settings need to be valid.

::

    ; For Kerberos authentication
    ; the principal to connect with
    principal=koji/kojira@EXAMPLE.COM
    ; The location of the keytab for the principal above
    keytab=/etc/kojira.keytab

``/etc/sysconfig/kojira``
    The local user kojira runs as needs to be able to read and write to
    ``/mnt/koji/repos/``. If the volume that directory resides on is
    root-squashed or otherwise unmodifiable by root, you can set ``RUNAS=`` to
    a user that has the required privileges.

Start Kojira
------------

::

    root@localhost$ service kojira start

Check ``/var/log/kojira/kojira.log`` to verify that kojira has started
successfully.

Bootstrapping the Koji build environment
========================================

For instructions on importing packages and preparing Koji to run builds, see
:doc:`Server Bootstrap <server_bootstrap>`.

For instructions on using External Repos and preparing Koji to run builds, see
:doc:`External Repo Server Bootstrap <external_repo_server_bootstrap>`.

Useful scripts and config files for setting up a Koji instance are available
`here <http://fedora.danny.cz/koji/>`_.

Minutia and Miscellany
======================
Please see :doc:`KojiMisc <misc>` for additional details and notes about
operating a koji server.

.. _dnf: https://fedoraproject.org/wiki/Dnf
.. _yum: https://fedoraproject.org/wiki/Yum
.. _createrepo: http://createrepo.baseurl.org/
.. _mock: https://fedoraproject.org/wiki/Mock
.. _Apache mod_ssl documentation:
    https://httpd.apache.org/docs/trunk/mod/mod_ssl.html#ssloptions 
