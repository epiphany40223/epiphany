import com.google.api.client.auth.oauth2.Credential;
import com.google.api.client.extensions.java6.auth.oauth2.AuthorizationCodeInstalledApp;
import com.google.api.client.extensions.jetty.auth.oauth2.LocalServerReceiver;
import com.google.api.client.googleapis.auth.oauth2.GoogleAuthorizationCodeFlow;
import com.google.api.client.googleapis.auth.oauth2.GoogleClientSecrets;
import com.google.api.client.googleapis.javanet.GoogleNetHttpTransport;
import com.google.api.client.http.HttpTransport;
import com.google.api.client.json.jackson2.JacksonFactory;
import com.google.api.client.json.JsonFactory;
import com.google.api.client.util.store.FileDataStoreFactory;

import com.google.api.services.admin.directory.DirectoryScopes;
import com.google.api.services.admin.directory.model.*;
import com.google.api.services.admin.directory.Directory;

import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.util.Arrays;
import java.util.List;

public class PDSGoogleGroupConnector {
    /** Application name. */
    private static final String APPLICATION_NAME =
	"Directory API Java PDSGoogleGroupConnector";

    /** Directory to store user credentials for this application. */
    private static final java.io.File DATA_STORE_DIR =
	new java.io.File(System.getProperty("user.home"),
			 ".credentials/admin-directory_v1-java-quickstart");

    /** Global instance of the {@link FileDataStoreFactory}. */
    private static FileDataStoreFactory DATA_STORE_FACTORY;

    /** Global instance of the JSON factory. */
    private static final JsonFactory JSON_FACTORY =
	JacksonFactory.getDefaultInstance();

    /** Global instance of the HTTP transport. */
    private static HttpTransport HTTP_TRANSPORT;

    /** Global instance of the scopes required by this quickstart.
     *
     * If modifying these scopes, delete your previously saved credentials
     * at ~/.credentials/admin-directory_v1-java-quickstart
     */
    // JMS Need to make these more fine-grained
    private static final List<String> SCOPES =
	Arrays.asList(// List domain users
		      DirectoryScopes.ADMIN_DIRECTORY_USER_READONLY,
		      // Listing domain groups
		      DirectoryScopes.ADMIN_DIRECTORY_GROUP_READONLY,
		      // Listing + modifying members of domain groups
		      DirectoryScopes.ADMIN_DIRECTORY_GROUP_MEMBER);

    static {
	try {
	    HTTP_TRANSPORT = GoogleNetHttpTransport.newTrustedTransport();
	    DATA_STORE_FACTORY = new FileDataStoreFactory(DATA_STORE_DIR);
	} catch (Throwable t) {
	    t.printStackTrace();
	    System.exit(1);
	}
    }

    /**
     * Creates an authorized Credential object.
     * @return an authorized Credential object.
     * @throws IOException
     */
    public static Credential authorize() throws IOException {
	// Load client secrets.
	InputStream in =
	    PDSGoogleGroupConnector.class.getResourceAsStream("/client_secret.json");
	GoogleClientSecrets clientSecrets =
	    GoogleClientSecrets.load(JSON_FACTORY, new InputStreamReader(in));

	// Build flow and trigger user authorization request.
	GoogleAuthorizationCodeFlow flow =
	    new GoogleAuthorizationCodeFlow.Builder(HTTP_TRANSPORT,
						    JSON_FACTORY,
						    clientSecrets, SCOPES)
	    .setDataStoreFactory(DATA_STORE_FACTORY)
	    .setAccessType("offline")
	    .build();
	Credential credential =
	    new AuthorizationCodeInstalledApp(flow,
					      new LocalServerReceiver()).authorize("user");
	System.out.println("Credentials saved to " +
			   DATA_STORE_DIR.getAbsolutePath());
	return credential;
    }

    /**
     * Build and return an authorized Admin SDK Directory client service.
     * @return an authorized Directory client service
     * @throws IOException
     */
    public static Directory getDirectoryService() throws IOException {
	Credential credential = authorize();
	return new Directory.Builder(HTTP_TRANSPORT, JSON_FACTORY,
				     credential)
	    .setApplicationName(APPLICATION_NAME)
	    .build();
    }

    public static void usersTest(Directory service) throws IOException {
	// Print the first 10 users in the domain.
	int n = 10;
	Users result = service.users().list()
	    .setCustomer("my_customer")
	    .setMaxResults(n)
	    .setOrderBy("email")
	    .execute();

	List<User> users = result.getUsers();
	if (users == null || users.size() == 0) {
	    System.out.println("No users found.");
	} else {
	    System.out.println(String.format("===== First %d users in the domain", n));
	    for (User user : users) {
		System.out.println(user.getName().getFullName());
	    }
	}
    }

    public static void membersTest(Directory service, Group group) throws IOException {
	System.out.println("==== continue here to print members of the group");
        // JMS This will be paginated
        // JMS continue here
        // JMS see https://developers.google.com/admin-sdk/directory/v1/guides/manage-group-members ...?
    }

    public static void groupsTest(Directory service) throws IOException {
	System.out.println("===== Groups in the domain");

	Groups result = service.groups().list()
	    .setCustomer("my_customer")
	    .execute();
	List<Group> groups = result.getGroups();
	if (groups == null || groups.size() == 0) {
	    System.out.println("===== No groups in domain");
	    return;
	}

	for (Group group : groups) {
	    System.out.println(String.format("Group: %s:\n\tAddr: %s\n\tMembers: %d\n\tKind: %s\n\tEtag: %s\n\tID: %s",
					     group.getName(),
					     group.getEmail(),
					     group.getDirectMembersCount(),
					     group.getKind(),
					     group.getEtag(),
					     group.getId()));

	    Boolean printedAliasesTitle = false;
	    List<java.lang.String> aliases;
	    aliases = group.getAliases();
	    if (aliases != null && aliases.size() > 0) {
		System.out.println("\tAliases:");
		printedAliasesTitle = true;
		for (String alias : aliases) {
		    System.out.println("\t\t" + alias);
		}
	    }

	    aliases = group.getNonEditableAliases();
	    if (aliases != null && aliases.size() > 0) {
		if (!printedAliasesTitle) {
		    System.out.println("\tAliases:");
		    printedAliasesTitle = true;
		}
		for (String alias : aliases) {
		    System.out.println("\t\t" + alias);
		}
	    }

	    if (!printedAliasesTitle) {
		System.out.println("\tAliases: none");
	    }

	    // Get the members of this group
	    membersTest(service, group);
	}
    }

    public static void main(String[] args) throws IOException {
	// Build a new authorized API client service.
	Directory service = getDirectoryService();

	usersTest(service);
	groupsTest(service);
    }
}
