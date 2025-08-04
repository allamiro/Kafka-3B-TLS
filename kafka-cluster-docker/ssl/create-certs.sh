#!/bin/bash

set -eu

PASSWORD="supersecret"
VALIDITY_IN_DAYS=3650
CA_WORKING_DIRECTORY="certificate-authority"
TRUSTSTORE_WORKING_DIRECTORY="truststore"
KEYSTORE_WORKING_DIRECTORY="keystore"
CA_KEY_FILE="ca-key"
CA_CERT_FILE="ca-cert"
DEFAULT_TRUSTSTORE_FILE="kafka.truststore.jks"
KEYSTORE_SIGN_REQUEST="cert-file"
KEYSTORE_SIGN_REQUEST_SRL="ca-cert.srl"
KEYSTORE_SIGNED_CERT="cert-signed"

echo "Welcome to the Kafka SSL certificate authority, key store and trust store generator script."

# Clean up and create directories

# Generate CA key and certificate
echo "Creating Certificate Authority..."
openssl req -new -x509 -keyout $CA_WORKING_DIRECTORY/ca-key -out $CA_WORKING_DIRECTORY/ca-cert -days $VALIDITY -nodes -subj "/C=US/ST=CA/L=San Francisco/O=Test/CN=kafka-ca"

# Create truststore with CA certificate
echo "Creating truststore..."
keytool -keystore $TRUSTSTORE_DIR/kafka.truststore.jks -alias ca-cert -import -file $CA_WORKING_DIRECTORY/ca-cert -storepass $PASSWORD -noprompt

# Generate broker certificates
for i in 0 1 2; do
    echo "Creating certificate for broker-$((i+1))..."
    
    # Generate private key and certificate signing request
    openssl req -newkey rsa:2048 -nodes -keyout broker-$i-key.pem -out broker-$i.csr -subj "/C=US/ST=CA/L=San Francisco/O=Test/CN=broker-$((i+1))"
    
    # Sign certificate with CA
    openssl x509 -req -in broker-$i.csr -CA $CA_WORKING_DIRECTORY/ca-cert -CAkey $CA_WORKING_DIRECTORY/ca-key -out broker-$i-cert.pem -days $VALIDITY -CAcreateserial
    
    # Create PKCS12 keystore
    openssl pkcs12 -export -in broker-$i-cert.pem -inkey broker-$i-key.pem -out broker-$i.p12 -name broker-$i -password pass:$PASSWORD
    
    # Convert to JKS format
    keytool -importkeystore -deststorepass $PASSWORD -destkeypass $PASSWORD -destkeystore $KEYSTORE_DIR/kafka-$i.server.keystore.jks -srckeystore broker-$i.p12 -srcstoretype PKCS12 -srcstorepass $PASSWORD -alias broker-$i
    
    # Import CA certificate into keystore
    keytool -keystore $KEYSTORE_DIR/kafka-$i.server.keystore.jks -alias ca-cert -import -file $CA_WORKING_DIRECTORY/ca-cert -storepass $PASSWORD -noprompt
    
    # Create credential files
    echo $PASSWORD > $KEYSTORE_DIR/kafka-${i}_keystore_creds
    echo $PASSWORD > $KEYSTORE_DIR/kafka-${i}_sslkey_creds
    
    # Clean up temporary files
    rm -f broker-$i-key.pem broker-$i.csr broker-$i-cert.pem broker-$i.p12
done

# Clean up CA files
rm -f $CA_WORKING_DIRECTORY/ca-key $CA_WORKING_DIRECTORY/ca-cert $CA_WORKING_DIRECTORY/ca-cert.srl

echo "SSL certificates generated successfully!"
echo "Files created:"
ls -la $KEYSTORE_DIR/ $TRUSTSTORE_DIR/
echo "Files created:"
echo "Certificate Authority:"
ls -la $CA_WORKING_DIRECTORY/
echo "Truststore:"
ls -la $TRUSTSTORE_DIR/
ls -la $KEYSTORE_WORKING_DIRECTORY/
echo ""
echo "Ready to use with Apache Kafka SSL configuration!"